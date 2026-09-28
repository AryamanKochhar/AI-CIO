"""Fixed-deposit holdings CRUD + intelligence summary."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.db.models import FixedDeposit
from ai_cio.services.fd.rates import get_fd_rates, match_bank_rate
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError

ZERO = Decimal("0")


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


def _rate(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("Interest rate must be a number") from exc
    if rate < 0 or rate > 50:
        raise DomainError("Interest rate looks invalid")
    return rate


def _money_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def serialize_fd(row: FixedDeposit) -> dict[str, Any]:
    return {
        "id": row.id,
        "bank_name": row.bank_name,
        "account_label": row.account_label,
        "principal": _money_str(row.principal),  # type: ignore[arg-type]
        "interest_rate_pa": _money_str(row.interest_rate_pa) if row.interest_rate_pa is not None else None,  # type: ignore[arg-type]
        "tenure_months": row.tenure_months,
        "start_date": row.start_date,
        "maturity_date": row.maturity_date,
        "compounding": row.compounding,
        "is_senior_citizen": bool(row.is_senior_citizen),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_fixed_deposits(db: Session, user_id: int) -> list[dict[str, Any]]:
    get_user(db, user_id)
    rows = (
        db.query(FixedDeposit)
        .filter(FixedDeposit.user_id == user_id)
        .order_by(FixedDeposit.bank_name, FixedDeposit.id)
        .all()
    )
    return [serialize_fd(r) for r in rows]


def create_fixed_deposit(db: Session, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    get_user(db, user_id)
    bank = (payload.get("bank_name") or "").strip()
    if not bank:
        raise DomainError("bank_name is required")
    principal = _money(payload.get("principal"))
    if principal is None or principal <= 0:
        raise DomainError("principal is required and must be positive")
    tenure = payload.get("tenure_months")
    tenure_i = int(tenure) if tenure not in (None, "") else None
    row = FixedDeposit(
        user_id=user_id,
        bank_name=bank,
        account_label=(payload.get("account_label") or "").strip() or None,
        principal=principal,
        interest_rate_pa=_rate(payload.get("interest_rate_pa")),
        tenure_months=tenure_i,
        start_date=(payload.get("start_date") or "").strip() or None,
        maturity_date=(payload.get("maturity_date") or "").strip() or None,
        compounding=(payload.get("compounding") or "").strip() or "cumulative",
        is_senior_citizen=bool(payload.get("is_senior_citizen")),
        notes=(payload.get("notes") or "").strip() or None,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return serialize_fd(row)


def delete_fixed_deposit(db: Session, user_id: int, fd_id: int) -> None:
    get_user(db, user_id)
    row = (
        db.query(FixedDeposit)
        .filter(FixedDeposit.user_id == user_id, FixedDeposit.id == fd_id)
        .one_or_none()
    )
    if row is None:
        raise DomainError("Fixed deposit not found")
    db.delete(row)
    db.flush()


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_fd_intelligence(
    db: Session,
    user_id: int,
    *,
    liquid: Decimal | None = None,
    force_refresh_rates: bool = False,
) -> dict[str, Any]:
    fds = list_fixed_deposits(db, user_id)
    rates_payload = get_fd_rates(db, force_refresh=force_refresh_rates)
    market_rates = rates_payload.get("rates") or []

    total_principal = ZERO
    by_bank: dict[str, Decimal] = {}
    enriched: list[dict[str, Any]] = []
    comments: list[str] = []
    opportunities: list[dict[str, Any]] = []
    maturity_alerts: list[dict[str, Any]] = []
    today = date.today()

    for fd in fds:
        principal = Decimal(fd["principal"] or "0")
        total_principal += principal
        by_bank[fd["bank_name"]] = by_bank.get(fd["bank_name"], ZERO) + principal
        market = match_bank_rate(fd["bank_name"], market_rates)
        own_rate = Decimal(fd["interest_rate_pa"]) if fd.get("interest_rate_pa") else None
        market_max = None
        if market and market.get("general_max"):
            try:
                market_max = Decimal(
                    str(
                        market["senior_max"]
                        if fd.get("is_senior_citizen") and market.get("senior_max")
                        else market["general_max"]
                    )
                )
            except (InvalidOperation, TypeError):
                market_max = None
        enriched.append(
            {
                **fd,
                "market_match": market,
                "rate_gap_pa": (
                    f"{(market_max - own_rate):.2f}"
                    if market_max is not None and own_rate is not None
                    else None
                ),
            }
        )

        mat = _parse_iso_date(fd.get("maturity_date"))
        if mat is not None:
            days = (mat - today).days
            if 0 <= days <= 60:
                maturity_alerts.append(
                    {
                        "type": "maturity_approaching",
                        "fd_id": fd["id"],
                        "bank_name": fd["bank_name"],
                        "days_to_maturity": days,
                        "principal": fd["principal"],
                        "reason": (
                            f"{fd['bank_name']} FD of ₹{principal:.0f} matures in {days} day(s). "
                            "Review renewal vs redeployment against current bank FD rates."
                        ),
                    }
                )

        if own_rate is not None and market_max is not None and market_max > own_rate + Decimal("0.25"):
            opportunities.append(
                {
                    "type": "rate_comparison",
                    "bank_name": fd["bank_name"],
                    "fd_id": fd["id"],
                    "your_rate_pa": f"{own_rate:.2f}",
                    "market_max_pa": f"{market_max:.2f}",
                    "gap_pa": f"{(market_max - own_rate):.2f}",
                    "reason": (
                        f"Your {fd['bank_name']} FD is booked at ~{own_rate:.2f}% p.a.; "
                        f"public comparison max for that bank is ~{market_max:.2f}% p.a. "
                        "Gap may reflect tenure/senior status — verify before any change. Not a sell instruction."
                    ),
                    "confidence": 0.45,
                }
            )

    if total_principal > 0:
        comments.append(f"You have ₹{total_principal:.0f} across {len(fds)} fixed deposit(s).")
    else:
        comments.append("No fixed deposits recorded yet — add bank FDs on the FD page to compare rates.")

    if liquid is not None and liquid > 0:
        comments.append(
            f"Liquid savings (undeployed cash) on file: ₹{liquid:.0f}. "
            "Compare emergency buffer needs before parking surplus in FDs."
        )
        if total_principal == 0 and liquid >= Decimal("50000"):
            opportunities.append(
                {
                    "type": "idle_cash",
                    "bank_name": None,
                    "amount": f"{liquid:.2f}",
                    "reason": (
                        f"You have ~₹{liquid:.0f} liquid savings and no recorded FDs. "
                        "If this exceeds your emergency buffer, comparing bank FD rates may be relevant — "
                        "subject to liquidity needs. Not a recommendation to open an FD."
                    ),
                    "confidence": 0.4,
                }
            )

    if maturity_alerts:
        comments.append(f"{len(maturity_alerts)} FD(s) mature within 60 days.")

    top_rates = sorted(
        [r for r in market_rates if r.get("general_max")],
        key=lambda r: Decimal(str(r["general_max"])),
        reverse=True,
    )[:5]

    available = bool(fds) or bool(market_rates)
    return {
        "available": available,
        "agent": "fd_agent",
        "status": "success" if available else "insufficient_data",
        "summary": {
            "fd_count": len(fds),
            "total_principal": f"{total_principal:.2f}",
            "bank_count": len(by_bank),
            "liquid_cash": _money_str(liquid),
            "combined_cash_and_fd": _money_str((liquid or ZERO) + total_principal),
        },
        "fixed_deposits": enriched,
        "by_bank": [
            {"bank_name": k, "principal": f"{v:.2f}"}
            for k, v in sorted(by_bank.items(), key=lambda x: x[1], reverse=True)
        ],
        "market_rates": rates_payload,
        "top_market_rates": top_rates,
        "opportunities": opportunities,
        "maturity_alerts": maturity_alerts,
        "comments": comments,
        "assumptions": [
            "Market rates are scraped/cached public comparison ranges, not bank-quoted bookings.",
            "Your FD rates are user-entered; missing rates are not invented.",
            "DICGC covers deposits up to ₹5 lakh per bank per depositor (educational reminder).",
        ],
        "disclaimer": (
            "Educational FD overview only — not investment advice or a recommendation to open/close deposits. "
            "Confirm rates and terms with the bank."
        ),
        "as_of": datetime.utcnow().isoformat() + "Z",
    }
