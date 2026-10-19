"""CAS / CDSL persistence on canonical Postgres. Parsers remain pure functions."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from ai_cio.db.models import Document, Fund, Holding, PortfolioSnapshot, SourcePage, Transaction
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.settings import PARSER_VERSION
from domain.parser import ParseResult, parse_cas

ZERO = Decimal("0")
PORTFOLIO_KINDS = frozenset({"cas_pdf", "cdsl_statement", "demo_portfolio"})


def _dec(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def _opt_dec(value):
    if value is None:
        return None
    return Decimal(str(value))


def find_document_by_checksum(db: Session, user_id: int, checksum: str) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.checksum == checksum,
            Document.status.in_(("extracted", "needs_review", "pending")),
        )
        .order_by(Document.ingested_at.desc())
        .first()
    )


def _serialize_cdsl_metadata(metadata) -> dict:
    return {
        "cas_id": metadata.cas_id,
        "statement_start": metadata.statement_start,
        "statement_end": metadata.statement_end,
        "holder_name": metadata.holder_name,
        "total_portfolio_value": str(metadata.total_portfolio_value) if metadata.total_portfolio_value is not None else None,
        "equity_value": str(metadata.equity_value) if metadata.equity_value is not None else None,
        "mutual_fund_value": str(metadata.mutual_fund_value) if metadata.mutual_fund_value is not None else None,
        "status": metadata.status,
        "successful_sections": list(metadata.successful_sections),
        "failed_sections": list(metadata.failed_sections),
        "demat_accounts": [
            {
                "depository": a.depository,
                "dp_name": a.dp_name,
                "dp_id": a.dp_id,
                "client_id": a.client_id,
                "bo_id": a.bo_id,
                "account_status": a.account_status,
                "value": str(a.value) if a.value is not None else None,
                "isin_count": a.isin_count,
            }
            for a in metadata.demat_accounts
        ],
        "allocation": [
            {
                "asset_class": a.asset_class,
                "value": str(a.value),
                "percentage": str(a.percentage) if a.percentage is not None else None,
            }
            for a in metadata.allocation
        ],
        "snapshots": [
            {
                "month_year": s.month_year,
                "valuation": str(s.valuation),
                "change_amount": str(s.change_amount) if s.change_amount is not None else None,
                "change_pct": str(s.change_pct) if s.change_pct is not None else None,
            }
            for s in metadata.snapshots
        ],
    }


def persist_parse_result(
    db: Session,
    user_id: int,
    result: ParseResult,
    filename: str,
    checksum: str | None = None,
    *,
    kind: str = "cas_pdf",
    parser_version: str | None = None,
    metadata: dict | None = None,
) -> Document:
    """Insert a new document and its rows. Never deletes other documents."""
    get_user(db, user_id)
    if not result.holdings:
        raise DomainError("Ingestion stopped: no holdings confidently parsed")
    document = Document(
        user_id=user_id,
        kind=kind,
        filename=filename,
        parser_version=parser_version or PARSER_VERSION,
        checksum=checksum,
        warning_json=list(result.warnings) if result.warnings else None,
        metadata_json=metadata,
    )
    db.add(document)
    db.flush()

    for page, text in result.pages.items():
        db.add(SourcePage(document_id=document.id, user_id=user_id, page=page, text=text))

    fund_ids: dict[tuple, int] = {}

    def fund_key(record) -> tuple:
        return (record.amc, record.folio, record.scheme_name, record.isin)

    def ensure_fund(record) -> int:
        key = fund_key(record)
        if key in fund_ids:
            return fund_ids[key]
        fund = Fund(
            user_id=user_id,
            document_id=document.id,
            amc=record.amc,
            folio=record.folio,
            scheme_name=record.scheme_name,
            isin=record.isin,
        )
        db.add(fund)
        db.flush()
        fund_ids[key] = fund.id
        return fund.id

    for holding in result.holdings:
        asset_class = getattr(holding, "asset_class", None)
        if asset_class is None and holding.amc == "EQUITY":
            asset_class = "equity"
        elif asset_class is None:
            asset_class = "mutual_fund"
        db.add(
            Holding(
                user_id=user_id,
                document_id=document.id,
                fund_id=ensure_fund(holding),
                opening_units=holding.opening_units,
                closing_units=holding.closing_units,
                nav=holding.nav,
                valuation=holding.valuation,
                valuation_date=holding.valuation_date,
                asset_class=asset_class,
                invested_amount=getattr(holding, "invested_amount", None),
                unrealised_pl=getattr(holding, "unrealised_pl", None),
                unrealised_pl_pct=getattr(holding, "unrealised_pl_pct", None),
                source_page=holding.source_page,
            )
        )
    for txn in result.transactions:
        db.add(
            Transaction(
                user_id=user_id,
                document_id=document.id,
                fund_id=ensure_fund(txn),
                date=txn.date,
                transaction_type=txn.transaction_type,
                description=txn.description,
                amount=txn.amount,
                units=txn.units,
                nav=txn.nav,
                unit_balance=txn.unit_balance,
                source_page=txn.source_page,
            )
        )

    snapshots = (metadata or {}).get("snapshots") or []
    for snap in snapshots:
        db.add(
            PortfolioSnapshot(
                user_id=user_id,
                document_id=document.id,
                month_year=snap["month_year"],
                valuation=_dec(snap["valuation"]),
                change_amount=_opt_dec(snap.get("change_amount")),
                change_pct=_opt_dec(snap.get("change_pct")),
            )
        )
    db.flush()
    return document


def ingest_cas(
    db: Session, user_id: int, pdf_path: str | Path, filename: str | None = None
) -> tuple[Document, ParseResult]:
    path = Path(pdf_path)
    checksum = sha256(path.read_bytes()).hexdigest()
    result = parse_cas(path)
    document = persist_parse_result(db, user_id, result, filename or path.name, checksum)
    return document, result


def ingest_cdsl_cas(
    db: Session, user_id: int, pdf_path: str | Path, filename: str | None = None
) -> tuple[Document, object, bool]:
    """Parse and persist a CDSL CAS. Returns (document, result, already_processed)."""
    from domain.documents.cdsl import PARSER_VERSION as CDSL_VERSION, parse_cdsl_cas

    path = Path(pdf_path)
    checksum = sha256(path.read_bytes()).hexdigest()
    existing = find_document_by_checksum(db, user_id, checksum)
    if existing is not None and existing.kind == "cdsl_statement" and existing.status in {
        "extracted",
        "needs_review",
    }:
        return existing, None, True

    result = parse_cdsl_cas(path)
    if not result.holdings:
        raise DomainError("Ingestion stopped: no holdings confidently parsed from CDSL CAS")
    meta = _serialize_cdsl_metadata(result.metadata)
    document = persist_parse_result(
        db,
        user_id,
        result,
        filename or path.name,
        checksum,
        kind="cdsl_statement",
        parser_version=CDSL_VERSION,
        metadata=meta,
    )
    return document, result, False


def latest_document_id(db: Session, user_id: int) -> int | None:
    row = (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.kind.in_(tuple(PORTFOLIO_KINDS)),
            Document.status.in_(("extracted", "needs_review")),
        )
        .order_by(Document.ingested_at.desc())
        .first()
    )
    if row:
        return row.id
    # Fallback: any portfolio kind (legacy CAS rows may still be pending status from direct ingest)
    row = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.kind.in_(tuple(PORTFOLIO_KINDS)))
        .order_by(Document.ingested_at.desc())
        .first()
    )
    return row.id if row else None


def _scoped_document_id(db: Session, user_id: int, document_id: int | None) -> int | None:
    if document_id is not None:
        doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
        if doc is None:
            raise DomainError("Document not found for this user")
        return document_id
    return latest_document_id(db, user_id)


def list_holdings(db: Session, user_id: int, document_id: int | None = None) -> list[dict]:
    get_user(db, user_id)
    scoped = _scoped_document_id(db, user_id, document_id)
    if scoped is None:
        return []
    rows = (
        db.query(Holding, Fund)
        .join(Fund, Holding.fund_id == Fund.id)
        .filter(Holding.user_id == user_id, Holding.document_id == scoped)
        .all()
    )
    holdings = []
    for holding, fund in rows:
        holdings.append(
            {
                "amc": fund.amc,
                "folio": fund.folio,
                "scheme_name": fund.scheme_name,
                "isin": fund.isin,
                "closing_units": _dec(holding.closing_units),
                "nav": _dec(holding.nav),
                "valuation": _dec(holding.valuation),
                "valuation_date": holding.valuation_date,
                "asset_class": holding.asset_class or ("equity" if fund.amc == "EQUITY" else "mutual_fund"),
                "invested_amount": _opt_dec(holding.invested_amount),
                "unrealised_pl": _opt_dec(holding.unrealised_pl),
                "unrealised_pl_pct": _opt_dec(holding.unrealised_pl_pct),
                "source_page": holding.source_page,
                "user_id": holding.user_id,
                "document_id": holding.document_id,
            }
        )
    holdings.sort(key=lambda h: h["valuation"], reverse=True)
    return holdings


def list_transactions(
    db: Session,
    user_id: int,
    document_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fund: str | None = None,
    amc: str | None = None,
    transaction_type: str | None = None,
) -> list[dict]:
    get_user(db, user_id)
    scoped = _scoped_document_id(db, user_id, document_id)
    if scoped is None:
        return []
    query = (
        db.query(Transaction, Fund)
        .join(Fund, Transaction.fund_id == Fund.id)
        .filter(Transaction.user_id == user_id, Transaction.document_id == scoped)
    )
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if fund:
        query = query.filter(Fund.scheme_name.ilike(f"%{fund}%"))
    if amc:
        query = query.filter(Fund.amc.ilike(f"%{amc}%"))
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    rows = query.order_by(Transaction.date).all()
    out = []
    for txn, fund_row in rows:
        out.append(
            {
                "amc": fund_row.amc,
                "folio": fund_row.folio,
                "scheme_name": fund_row.scheme_name,
                "isin": fund_row.isin,
                "date": txn.date,
                "transaction_type": txn.transaction_type,
                "description": txn.description,
                "amount": _opt_dec(txn.amount),
                "units": _opt_dec(txn.units),
                "nav": _opt_dec(txn.nav),
                "unit_balance": _opt_dec(txn.unit_balance),
                "source_page": txn.source_page,
                "user_id": txn.user_id,
                "document_id": txn.document_id,
            }
        )
    return out


def holdings_on_page(db: Session, user_id: int, page: int, document_id: int | None = None) -> dict:
    """Traceability without raw CAS page text."""
    get_user(db, user_id)
    scoped = _scoped_document_id(db, user_id, document_id)
    if scoped is None:
        return {"source_document": None, "page": page, "holdings": []}
    document = db.query(Document).filter(Document.id == scoped).one()
    rows = (
        db.query(Holding, Fund)
        .join(Fund, Holding.fund_id == Fund.id)
        .filter(
            Holding.user_id == user_id,
            Holding.document_id == scoped,
            Holding.source_page == page,
        )
        .all()
    )
    return {
        "source_document": document.filename,
        "document_id": document.id,
        "page": page,
        "holdings": [
            {
                "amc": fund.amc,
                "folio": fund.folio,
                "scheme_name": fund.scheme_name,
                "valuation": _dec(holding.valuation),
                "source_page": holding.source_page,
            }
            for holding, fund in rows
        ],
    }


def document_count(db: Session, user_id: int) -> int:
    return db.query(Document).filter(Document.user_id == user_id).count()


def get_document(db: Session, user_id: int, document_id: int) -> Document:
    get_user(db, user_id)
    row = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if row is None:
        raise DomainError("Document not found for this user")
    return row


def list_portfolio_snapshots(db: Session, user_id: int, document_id: int | None = None) -> list[dict]:
    get_user(db, user_id)
    scoped = _scoped_document_id(db, user_id, document_id)
    if scoped is None:
        return []
    rows = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.user_id == user_id, PortfolioSnapshot.document_id == scoped)
        .order_by(PortfolioSnapshot.id)
        .all()
    )
    return [
        {
            "month_year": row.month_year,
            "valuation": _dec(row.valuation),
            "change_amount": _opt_dec(row.change_amount),
            "change_pct": _opt_dec(row.change_pct),
            "document_id": row.document_id,
        }
        for row in rows
    ]
