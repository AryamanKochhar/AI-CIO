"""Goal hit-likelihood estimates from Twin finances + goal targets.

Educational projections with explicit return assumptions — not guarantees.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0")
Q2 = Decimal("0.01")

# Stated planning assumptions (documented in every result).
DEFAULT_ANNUAL_RETURN = Decimal("0.10")  # 10% nominal, illustrative
DEFAULT_INFLATION = Decimal("0.05")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(Q2, rounding=ROUND_HALF_UP)}"


def _years_to_target(target_date: str | None, horizon_years: Any = None) -> float | None:
    if horizon_years not in (None, ""):
        try:
            return float(horizon_years)
        except (TypeError, ValueError):
            pass
    if not target_date:
        return None
    raw = str(target_date).strip()
    try:
        if len(raw) == 7:
            raw = f"{raw}-01"
        target = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    days = (target - today).days
    if days <= 0:
        return 0.0
    return round(days / 365.25, 2)


def _band(coverage: Decimal | None) -> str:
    if coverage is None:
        return "unknown"
    if coverage >= Decimal("1.00"):
        return "likely"
    if coverage >= Decimal("0.75"):
        return "possible"
    if coverage >= Decimal("0.50"):
        return "at_risk"
    return "unlikely"


def _fv_lump(present: Decimal, annual_rate: Decimal, years: float) -> Decimal:
    if years <= 0:
        return present
    factor = (Decimal("1") + annual_rate) ** Decimal(str(years))
    return present * factor


def _fv_annuity(pmt: Decimal, annual_rate: Decimal, years: float) -> Decimal:
    if years <= 0 or pmt <= 0:
        return ZERO
    months = Decimal(str(years)) * Decimal("12")
    r_m = (Decimal("1") + annual_rate) ** (Decimal("1") / Decimal("12")) - Decimal("1")
    if r_m == 0:
        return pmt * months
    return pmt * (((Decimal("1") + r_m) ** months - Decimal("1")) / r_m)


def _required_pmt(need: Decimal, annual_rate: Decimal, years: float) -> Decimal | None:
    if years <= 0:
        return None
    if need <= 0:
        return ZERO
    months = Decimal(str(years)) * Decimal("12")
    r_m = (Decimal("1") + annual_rate) ** (Decimal("1") / Decimal("12")) - Decimal("1")
    if r_m == 0:
        return (need / months).quantize(Q2)
    pmt = need * r_m / (((Decimal("1") + r_m) ** months) - Decimal("1"))
    return pmt.quantize(Q2, rounding=ROUND_HALF_UP)


def assess_goal(
    goal: dict[str, Any],
    *,
    monthly_surplus: Decimal | None,
    annual_return: Decimal = DEFAULT_ANNUAL_RETURN,
    inflation: Decimal = DEFAULT_INFLATION,
) -> dict[str, Any]:
    target = _dec(goal.get("target_amount"))
    current = _dec(goal.get("current_funding")) or ZERO
    years = _years_to_target(goal.get("target_date"), goal.get("horizon_years") or goal.get("years_remaining"))

    missing: list[str] = []
    if target is None:
        missing.append("target_amount")
    if years is None:
        missing.append("target_date_or_horizon")
    if monthly_surplus is None:
        missing.append("monthly_surplus_from_income_expenses")

    status = "unknown"
    coverage = None
    projected = None
    required_monthly = None
    likelihood_percent = None
    narrative = ""

    if target is not None and years is not None:
        fv_current = _fv_lump(current, annual_return, years)
        gap_after_growth = target - fv_current
        contrib = monthly_surplus if monthly_surplus is not None and monthly_surplus > 0 else ZERO
        fv_sip = _fv_annuity(contrib, annual_return, years) if monthly_surplus is not None else ZERO
        if monthly_surplus is not None:
            projected = fv_current + fv_sip
            coverage = (projected / target) if target > 0 else None
            status = _band(coverage)
            # Map coverage to a soft 0–100 likelihood score (capped)
            if coverage is not None:
                likelihood_percent = int(min(99, max(5, round(float(coverage) * 85))))
                if status == "likely":
                    likelihood_percent = max(likelihood_percent, 80)
            required_monthly = _required_pmt(max(ZERO, gap_after_growth), annual_return, years)
            narrative = (
                f"With ~₹{_money(contrib)}/mo surplus and an illustrative {float(annual_return)*100:.0f}% p.a. return, "
                f"projected corpus is ~₹{_money(projected)} vs target ₹{_money(target)} "
                f"({float(coverage)*100:.0f}% coverage) over ~{years} years."
                if coverage is not None
                else "Projection incomplete."
            )
        else:
            required_monthly = _required_pmt(max(ZERO, gap_after_growth), annual_return, years)
            narrative = (
                f"Income/expenses surplus unknown. To grow ₹{_money(current)} to ₹{_money(target)} "
                f"in ~{years} years at illustrative {float(annual_return)*100:.0f}% p.a., "
                f"you'd need about ₹{_money(required_monthly)}/mo (planning estimate)."
            )
            status = "unknown"
    else:
        narrative = "Need target amount and a target date (or horizon) to estimate goal likelihood."

    return {
        "goal_id": goal.get("id"),
        "goal_name": goal.get("name") or goal.get("goal_name"),
        "goal_type": goal.get("goal_type"),
        "target_amount": _money(target),
        "current_amount": _money(current),
        "years_remaining": years,
        "monthly_surplus_used": _money(monthly_surplus),
        "assumed_annual_return_percent": f"{(annual_return * 100).quantize(Q2)}",
        "assumed_inflation_percent": f"{(inflation * 100).quantize(Q2)}",
        "projected_corpus": _money(projected),
        "coverage_ratio": f"{coverage.quantize(Decimal('0.0001'))}" if coverage is not None else None,
        "likelihood_status": status,
        "likelihood_percent": likelihood_percent,
        "required_monthly_contribution": _money(required_monthly),
        "missing_inputs": missing,
        "narrative": narrative,
        "disclaimer": (
            "Illustrative math with stated return assumptions — not a prediction or SEBI advice. "
            "Actual markets, contributions, and taxes will differ."
        ),
    }


def assess_selected_goals(
    twin: dict[str, Any],
    goal_ids: list[int] | None = None,
    *,
    annual_return: Decimal | None = None,
) -> list[dict[str, Any]]:
    goals = list((twin.get("goals") or {}).get("items") or [])
    if goal_ids:
        id_set = {int(g) for g in goal_ids}
        goals = [g for g in goals if int(g.get("id")) in id_set]

    fp = twin.get("financial_position") or {}
    income = _dec((fp.get("income") or {}).get("value") if isinstance(fp.get("income"), dict) else fp.get("income"))
    expenses = _dec(
        (fp.get("expenses") or {}).get("value") if isinstance(fp.get("expenses"), dict) else fp.get("expenses")
    )
    surplus = None
    if income is not None and expenses is not None:
        surplus = income - expenses

    rate = annual_return if annual_return is not None else DEFAULT_ANNUAL_RETURN
    return [assess_goal(g, monthly_surplus=surplus, annual_return=rate) for g in goals]


def parse_goal_ids(constraints: dict[str, Any] | None) -> list[int]:
    if not constraints:
        return []
    raw = constraints.get("goal_ids")
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[int] = []
        for item in raw:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        out = []
        for p in parts:
            try:
                out.append(int(p))
            except ValueError:
                continue
        return out
    try:
        return [int(raw)]
    except (TypeError, ValueError):
        return []
