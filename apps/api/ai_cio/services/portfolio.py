"""CAS persistence on canonical Postgres. Parser remains a pure function."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from ai_cio.db.models import Document, Fund, Holding, SourcePage, Transaction
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError
from ai_cio.settings import PARSER_VERSION
from domain.parser import ParseResult, parse_cas

ZERO = Decimal("0")


def _dec(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def _opt_dec(value):
    if value is None:
        return None
    return Decimal(str(value))


def persist_parse_result(
    db: Session,
    user_id: int,
    result: ParseResult,
    filename: str,
    checksum: str | None = None,
) -> Document:
    """Insert a new document and its rows. Never deletes other documents."""
    get_user(db, user_id)
    if not result.holdings:
        raise DomainError("Ingestion stopped: no holdings confidently parsed")
    document = Document(
        user_id=user_id,
        kind="cas_pdf",
        filename=filename,
        parser_version=PARSER_VERSION,
        checksum=checksum,
        warning_json=list(result.warnings) if result.warnings else None,
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


def latest_document_id(db: Session, user_id: int) -> int | None:
    row = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.kind == "cas_pdf")
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
