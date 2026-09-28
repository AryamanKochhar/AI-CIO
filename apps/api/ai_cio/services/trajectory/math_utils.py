"""Shared deterministic FV math for trajectory projections (monthly compounding)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0")
Q2 = Decimal("0.01")


def d(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(Q2, rounding=ROUND_HALF_UP)}"


def monthly_rate(annual: Decimal) -> Decimal:
    return (Decimal("1") + annual) ** (Decimal("1") / Decimal("12")) - Decimal("1")


def fv_lump(present: Decimal, annual_rate: Decimal, years: float) -> Decimal:
    if years <= 0:
        return present
    return present * ((Decimal("1") + annual_rate) ** Decimal(str(years)))


def fv_annuity(pmt: Decimal, annual_rate: Decimal, years: float) -> Decimal:
    if years <= 0 or pmt <= 0:
        return ZERO
    months = Decimal(str(years)) * Decimal("12")
    r_m = monthly_rate(annual_rate)
    if r_m == 0:
        return pmt * months
    return pmt * (((Decimal("1") + r_m) ** months - Decimal("1")) / r_m)


def required_pmt(need: Decimal, annual_rate: Decimal, years: float) -> Decimal | None:
    if years <= 0:
        return None
    if need <= 0:
        return ZERO
    months = Decimal(str(years)) * Decimal("12")
    r_m = monthly_rate(annual_rate)
    if r_m == 0:
        return (need / months).quantize(Q2)
    pmt = need * r_m / (((Decimal("1") + r_m) ** months) - Decimal("1"))
    return pmt.quantize(Q2, rounding=ROUND_HALF_UP)


def project_path(
    *,
    principal: Decimal,
    monthly_pmt: Decimal,
    annual_rate: Decimal,
    years: int,
    contribution_growth_pa: Decimal = ZERO,
) -> list[dict[str, Any]]:
    """Year-by-year path with contributions vs growth split (monthly steps)."""
    points: list[dict[str, Any]] = []
    value = principal
    contrib_cum = ZERO
    pmt = monthly_pmt
    r_m = monthly_rate(annual_rate)
    for y in range(0, years + 1):
        if y == 0:
            points.append(
                {
                    "year": 0,
                    "value": money(value),
                    "contributions": money(ZERO),
                    "growth": money(ZERO),
                }
            )
            continue
        start = value
        year_contrib = ZERO
        for _m in range(12):
            value = value * (Decimal("1") + r_m) + pmt
            year_contrib += pmt
            contrib_cum += pmt
        # Contribution growth applied annually after each year
        if contribution_growth_pa > 0:
            pmt = pmt * (Decimal("1") + contribution_growth_pa)
        growth_cum = value - principal - contrib_cum
        points.append(
            {
                "year": y,
                "value": money(value),
                "contributions": money(contrib_cum),
                "growth": money(max(ZERO, growth_cum)),
                "year_contribution": money(year_contrib),
                "end_vs_start_growth": money(max(ZERO, value - start - year_contrib)),
            }
        )
    return points
