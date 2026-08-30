"""Document ingestion contract for CAS, NSDL, CDSL and other statements.

The parser adapter pattern lives here:

    Document → Document Type → Parser Adapter → Normalized Financial Data

Currently only CAS has a concrete adapter. NSDL/CDSL statements are stored and
tracked but explicitly marked as "parser support pending" so no holdings are
fabricated.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from ai_cio.db.models import DOCUMENT_KINDS, Document
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.services.portfolio import ingest_cas

SUPPORTED_KINDS = DOCUMENT_KINDS
PARSABLE_KINDS = {"cas_pdf"}


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
    if row.kind in PARSABLE_KINDS:
        row.status = "pending"
    else:
        row.status = "pending"
        row.validation_status = "unvalidated"
    db.flush()
    return row


def ingest_uploaded_document(
    db: Session,
    user_id: int,
    kind: str,
    filename: str,
    content: bytes | BinaryIO,
) -> tuple[Document, dict]:
    """Unified ingestion entry point.

    Returns (document, info_payload). For CAS the payload includes parsed
    holdings and transactions. For NSDL/CDSL the payload is empty and the
    document status stays pending with an explicit parser-pending notice.
    """
    get_user(db, user_id)
    if kind not in SUPPORTED_KINDS:
        raise DomainError(f"Unsupported document kind: {kind}")

    if isinstance(content, bytes):
        data = content
    else:
        data = content.read()

    if kind == "cas_pdf":
        from tempfile import NamedTemporaryFile

        tmp_path = None
        try:
            with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
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
        }

    # NSDL / CDSL / other: store and track, do not fabricate parsed data.
    document = register_document(db, user_id, kind, filename, data)
    document.status = "pending"
    document.validation_status = "unvalidated"
    db.flush()
    return document, {
        "holdings": 0,
        "transactions": 0,
        "warnings": [f"{kind} parser support pending; document stored for future processing."],
        "parser_pending": True,
    }


def serialize_document(row: Document) -> dict:
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
    }
