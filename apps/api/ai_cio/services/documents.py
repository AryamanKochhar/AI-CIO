"""Document ingestion contract for CAS, CDSL, NSDL and other statements.

Adapter pattern:

    Document → Document Type → Parser Adapter → Normalized Financial Data

CAS (MFCentral) and CDSL CAS have concrete adapters. NSDL remains stored with
parser-pending until its adapter is implemented.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO

from sqlalchemy.orm import Session

from ai_cio.db.models import DOCUMENT_KINDS, Document
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.services.portfolio import (
    find_document_by_checksum,
    ingest_cas,
    ingest_cdsl_cas,
    list_holdings,
    list_transactions,
)

SUPPORTED_KINDS = DOCUMENT_KINDS
PARSABLE_KINDS = {"cas_pdf", "cdsl_statement"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


def _checksum(data: bytes) -> str:
    return sha256(data).hexdigest()


def list_documents(db: Session, user_id: int) -> list[Document]:
    get_user(db, user_id)
    return db.query(Document).filter(Document.user_id == user_id).order_by(Document.ingested_at.desc()).all()


def create_document(
    db: Session,
    user_id: int,
    kind: str,
    filename: str,
    data: bytes,
) -> Document:
    get_user(db, user_id)
    if kind not in SUPPORTED_KINDS:
        raise DomainError(f"Unsupported document kind: {kind}")
    row = Document(
        user_id=user_id,
        kind=kind,
        filename=filename,
        checksum=_checksum(data),
        status="pending",
        validation_status="unvalidated",
    )
    db.add(row)
    db.flush()
    return row


def register_document(
    db: Session,
    user_id: int,
    kind: str,
    filename: str,
    data: bytes,
) -> Document:
    """Store a document without parsing. Used for kinds whose parser is pending."""
    row = create_document(db, user_id, kind, filename, data)
    row.status = "pending"
    row.validation_status = "unvalidated"
    db.flush()
    return row


def _write_temp_pdf(data: bytes) -> Path:
    with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        return Path(tmp.name)


def _summary_payload(document: Document, info: dict) -> dict:
    meta = document.metadata_json or {}
    return {
        "holdings": info.get("holdings", 0),
        "transactions": info.get("transactions", 0),
        "warnings": info.get("warnings", []),
        "parser_pending": info.get("parser_pending", False),
        "already_processed": info.get("already_processed", False),
        "summary": info.get("summary"),
        "statement_period": {
            "start": meta.get("statement_start"),
            "end": meta.get("statement_end"),
        }
        if meta.get("statement_start") or meta.get("statement_end")
        else info.get("statement_period"),
        "successful_sections": meta.get("successful_sections") or info.get("successful_sections"),
        "failed_sections": meta.get("failed_sections") or info.get("failed_sections"),
    }


def ingest_uploaded_document(
    db: Session,
    user_id: int,
    kind: str,
    filename: str,
    content: bytes | BinaryIO,
) -> tuple[Document, dict]:
    """Unified ingestion entry point."""
    get_user(db, user_id)
    if kind not in SUPPORTED_KINDS:
        raise DomainError(f"Unsupported document kind: {kind}")

    if isinstance(content, bytes):
        data = content
    else:
        data = content.read()

    if not filename.lower().endswith(".pdf") and kind in PARSABLE_KINDS:
        raise DomainError("Only PDF statements are supported for this document type")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DomainError("File is too large. Please upload a PDF under 25 MB.")
    if len(data) < 4:
        raise DomainError("File appears empty or invalid")

    checksum = _checksum(data)

    if kind == "cas_pdf":
        existing = find_document_by_checksum(db, user_id, checksum)
        if existing is not None and existing.kind == "cas_pdf" and existing.status in {
            "extracted",
            "needs_review",
        }:
            hs = list_holdings(db, user_id, existing.id)
            tx = list_transactions(db, user_id, existing.id)
            return existing, {
                "holdings": len(hs),
                "transactions": len(tx),
                "warnings": ["This statement has already been processed."],
                "parser_pending": False,
                "already_processed": True,
            }

        tmp_path = None
        try:
            tmp_path = _write_temp_pdf(data)
            document, result = ingest_cas(db, user_id, tmp_path, filename=filename)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()
        warnings = list(result.warnings) if result.warnings else []
        if warnings:
            document.status = "needs_review"
            document.validation_status = "partial"
        else:
            document.status = "extracted"
            document.validation_status = "valid"
        if document.warning_json is None:
            document.warning_json = []
        document.warning_json.extend(warnings)
        db.flush()
        return document, {
            "holdings": len(result.holdings),
            "transactions": len(result.transactions),
            "warnings": warnings,
            "parser_pending": False,
            "already_processed": False,
        }

    if kind == "cdsl_statement":
        tmp_path = None
        try:
            tmp_path = _write_temp_pdf(data)
            try:
                document, result, already = ingest_cdsl_cas(db, user_id, tmp_path, filename=filename)
            except ValueError as exc:
                raise DomainError(str(exc)) from exc
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

        if already:
            hs = list_holdings(db, user_id, document.id)
            tx = list_transactions(db, user_id, document.id)
            meta = document.metadata_json or {}
            return document, {
                "holdings": len(hs),
                "transactions": len(tx),
                "warnings": ["This statement has already been processed."],
                "parser_pending": False,
                "already_processed": True,
                "summary": _cdsl_summary(meta, len(hs), len(tx)),
                "statement_period": {
                    "start": meta.get("statement_start"),
                    "end": meta.get("statement_end"),
                },
                "successful_sections": meta.get("successful_sections"),
                "failed_sections": meta.get("failed_sections"),
            }

        assert result is not None
        meta = document.metadata_json or {}
        warnings = list(result.warnings) if result.warnings else []
        if result.metadata.status == "partial" or warnings:
            document.status = "needs_review"
            document.validation_status = "partial"
        else:
            document.status = "extracted"
            document.validation_status = "valid"
        if document.warning_json is None:
            document.warning_json = []
        document.warning_json.extend(warnings)
        db.flush()
        equity = sum(1 for h in result.holdings if (h.asset_class or h.amc) in {"equity", "EQUITY"})
        mf = len(result.holdings) - equity
        eq_tx = sum(1 for t in result.transactions if t.amc == "EQUITY")
        mf_tx = len(result.transactions) - eq_tx
        summary = {
            "demat_accounts": len(result.metadata.demat_accounts),
            "equity_holdings": equity,
            "mutual_fund_folios": mf,
            "demat_transactions": eq_tx,
            "mutual_fund_transactions": mf_tx,
            "portfolio_value": str(result.metadata.total_portfolio_value)
            if result.metadata.total_portfolio_value is not None
            else None,
            "equity_value": str(result.metadata.equity_value) if result.metadata.equity_value is not None else None,
            "mutual_fund_value": str(result.metadata.mutual_fund_value)
            if result.metadata.mutual_fund_value is not None
            else None,
            "cas_id": result.metadata.cas_id,
        }
        return document, {
            "holdings": len(result.holdings),
            "transactions": len(result.transactions),
            "warnings": warnings,
            "parser_pending": False,
            "already_processed": False,
            "summary": summary,
            "statement_period": {
                "start": result.metadata.statement_start,
                "end": result.metadata.statement_end,
            },
            "successful_sections": result.metadata.successful_sections,
            "failed_sections": result.metadata.failed_sections,
        }

    # NSDL / other: store and track, do not fabricate parsed data.
    document = register_document(db, user_id, kind, filename, data)
    document.status = "pending"
    document.validation_status = "unvalidated"
    db.flush()
    return document, {
        "holdings": 0,
        "transactions": 0,
        "warnings": [f"{kind} parser support pending; document stored for future processing."],
        "parser_pending": True,
        "already_processed": False,
    }


def _cdsl_summary(meta: dict, holdings: int, transactions: int) -> dict:
    return {
        "demat_accounts": len(meta.get("demat_accounts") or []),
        "equity_holdings": None,
        "mutual_fund_folios": None,
        "demat_transactions": None,
        "mutual_fund_transactions": None,
        "portfolio_value": meta.get("total_portfolio_value"),
        "equity_value": meta.get("equity_value"),
        "mutual_fund_value": meta.get("mutual_fund_value"),
        "cas_id": meta.get("cas_id"),
        "holdings": holdings,
        "transactions": transactions,
    }


def serialize_document(row: Document) -> dict:
    meta = row.metadata_json or {}
    return {
        "id": row.id,
        "user_id": row.user_id,
        "kind": row.kind,
        "filename": row.filename,
        "status": row.status,
        "validation_status": row.validation_status,
        "parser_version": row.parser_version,
        "warnings": row.warning_json or [],
        "ingested_at": row.ingested_at.isoformat() if row.ingested_at else None,
        "statement_period": {
            "start": meta.get("statement_start"),
            "end": meta.get("statement_end"),
        }
        if meta.get("statement_start") or meta.get("statement_end")
        else None,
        "metadata": {
            "cas_id": meta.get("cas_id"),
            "total_portfolio_value": meta.get("total_portfolio_value"),
            "equity_value": meta.get("equity_value"),
            "mutual_fund_value": meta.get("mutual_fund_value"),
            "demat_accounts": meta.get("demat_accounts"),
            "allocation": meta.get("allocation"),
            "successful_sections": meta.get("successful_sections"),
            "failed_sections": meta.get("failed_sections"),
        }
        if meta
        else None,
    }
