"""Cashflows and liabilities. Unknown values stay absent — never invented."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ai_cio.db.models import Cashflow, Liability
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError

KINDS = {"income", "expense", "liquid"}
CADENCES = {"monthly", "annual", "once"}


def _money(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("Amount must be a number") from exc
    if amount < 0:
        raise DomainError("Amount cannot be negative")
    return amount


def _money_str(value) -> str | None:
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def list_cashflows(db: Session, user_id: int) -> list[Cashflow]:
    get_user(db, user_id)
    return db.query(Cashflow).filter(Cashflow.user_id == user_id).order_by(Cashflow.id).all()


def list_liabilities(db: Session, user_id: int) -> list[Liability]:
    get_user(db, user_id)
    return db.query(Liability).filter(Liability.user_id == user_id).order_by(Liability.id).all()


def replace_finances(
    db: Session,
    user_id: int,
    income=None,
    expenses=None,
    liquid=None,
    cadence: str = "monthly",
    liabilities: list[dict] | None = None,
) -> None:
    get_user(db, user_id)
    if cadence not in CADENCES:
        raise DomainError("Cadence must be monthly, annual, or once")
    db.query(Cashflow).filter(Cashflow.user_id == user_id).delete()
    db.query(Liability).filter(Liability.user_id == user_id).delete()
    for kind, raw in (("income", income), ("expense", expenses), ("liquid", liquid)):
        amount = _money(raw)
        if amount is None:
            continue
        db.add(Cashflow(user_id=user_id, kind=kind, amount=amount, cadence=cadence))
    for item in liabilities or []:
        name = (item.get("name") or "").strip()
        balance = _money(item.get("balance"))
        if not name or balance is None:
            raise DomainError("Each liability needs a name and outstanding balance")
        db.add(
            Liability(
                user_id=user_id,
                name=name,
                balance=balance,
                monthly_payment=_money(item.get("monthly_payment")),
            )
        )
    db.flush()


def serialize_finances(db: Session, user_id: int) -> dict:
    flows = {row.kind: row for row in list_cashflows(db, user_id)}
    debts = list_liabilities(db, user_id)
    return {
        "income": _money_str(flows["income"].amount) if "income" in flows else None,
        "expenses": _money_str(flows["expense"].amount) if "expense" in flows else None,
        "liquid": _money_str(flows["liquid"].amount) if "liquid" in flows else None,
        "cadence": next((row.cadence for row in flows.values()), "monthly"),
        "liabilities": [
            {
                "id": row.id,
                "name": row.name,
                "balance": _money_str(row.balance),
                "monthly_payment": _money_str(row.monthly_payment),
            }
            for row in debts
        ],
    }
