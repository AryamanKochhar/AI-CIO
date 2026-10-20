"""Explicit convention math for regular option-free nominal bonds and T-bills.

Rates are decimals here; UI percentage conversion is the caller's responsibility.
These functions do not establish contractual terms, settlement, tax or suitability.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import math


def number(value, *, nonnegative: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and (not nonnegative or result >= 0) else None


def shift_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def year_fraction(start: date, end: date, convention: str) -> float:
    if convention == "30E/360":
        return ((end.year - start.year) * 360 + (end.month - start.month) * 30
                + min(end.day, 30) - min(start.day, 30)) / 360.0
    if convention == "ACT/365F":
        return (end - start).days / 365.0
    raise ValueError("Unsupported day-count convention")


def coupon_dates(maturity: date, settlement: date, frequency: int = 2) -> tuple[date, list[date]]:
    if frequency not in (1, 2, 4) or settlement >= maturity:
        raise ValueError("Future maturity and supported coupon frequency required")
    dates = []
    # Calculate each date from maturity, preventing February truncation drift.
    for offset in range(0, 401):
        day = shift_months(maturity, -offset * (12 // frequency))
        if day <= settlement:
            return day, list(reversed(dates))
        dates.append(day)
    raise ValueError("Coupon schedule exceeds bounded model horizon")


def fixed_cashflows(terms: dict, settlement: date) -> list[dict]:
    if terms.get("category") not in ("government_dated", "state_development", "corporate"):
        raise ValueError("This model supports nominal fixed-coupon bonds only")
    if not terms.get("regular_option_free") or not terms.get("cashflows_verified"):
        raise ValueError("Verified regular option-free contractual cashflows required")
    maturity = date.fromisoformat(terms["maturity_date"])
    frequency = int(terms["coupon_frequency"])
    face = number(terms.get("face_value"), nonnegative=True)
    rate = number(terms.get("coupon_rate_pct"), nonnegative=True)
    if not face or rate is None:
        raise ValueError("Positive face value and nonnegative coupon required")
    _, dates = coupon_dates(maturity, settlement, frequency)
    coupon = face * rate / 100.0 / frequency
    return [{"date": day.isoformat(), "coupon": coupon,
             "principal": face if day == maturity else 0.0,
             "amount": coupon + (face if day == maturity else 0.0)} for day in dates]


def accrued_interest(terms: dict, settlement: date) -> float:
    face, rate = number(terms.get("face_value")), number(terms.get("coupon_rate_pct"))
    if face is None or face <= 0 or rate is None or rate < 0:
        raise ValueError("Invalid coupon terms")
    previous, _ = coupon_dates(date.fromisoformat(terms["maturity_date"]), settlement,
                               int(terms["coupon_frequency"]))
    return face * rate / 100.0 * year_fraction(previous, settlement, terms["day_count"])


def full_price(quoted_price: float, basis: str, terms: dict, settlement: date) -> float:
    price = number(quoted_price)
    if price is None or price <= 0:
        raise ValueError("Positive finite quoted price required")
    if basis == "dirty":
        return price
    if basis == "clean":
        return price + accrued_interest(terms, settlement)
    raise ValueError("Verified clean or dirty price basis required")


def dirty_price_from_yield(terms: dict, settlement: date, annual_yield: float) -> float:
    frequency = int(terms["coupon_frequency"])
    if not math.isfinite(annual_yield) or annual_yield <= -frequency:
        raise ValueError("Yield outside supported compounding domain")
    base = 1 + annual_yield / frequency
    return sum(row["amount"] / base ** (frequency * year_fraction(
        settlement, date.fromisoformat(row["date"]), terms["day_count"]))
        for row in fixed_cashflows(terms, settlement))


def yield_to_maturity(terms: dict, settlement: date, dirty: float) -> float:
    price = number(dirty)
    if price is None or price <= 0:
        raise ValueError("Positive finite full price required")
    frequency = int(terms["coupon_frequency"])
    lower, upper = -0.95 * frequency, 1.0
    while dirty_price_from_yield(terms, settlement, upper) > price and upper < 256:
        upper *= 2
    if dirty_price_from_yield(terms, settlement, upper) > price:
        raise ValueError("Yield not bracketed within bounded solver")
    for _ in range(140):
        mid = (lower + upper) / 2
        if dirty_price_from_yield(terms, settlement, mid) > price:
            lower = mid
        else:
            upper = mid
    return (lower + upper) / 2


def rate_metrics(terms: dict, settlement: date, dirty: float) -> dict:
    ytm = yield_to_maturity(terms, settlement, dirty)
    bump = 0.0001
    p0 = dirty_price_from_yield(terms, settlement, ytm)
    down = dirty_price_from_yield(terms, settlement, ytm - bump)
    up = dirty_price_from_yield(terms, settlement, ytm + bump)
    duration = (down - up) / (2 * p0 * bump)
    convexity = (up + down - 2 * p0) / (p0 * bump * bump)
    frequency = int(terms["coupon_frequency"])
    return {"ytm_pct": ytm * 100, "modified_duration": duration,
            "macaulay_duration": duration * (1 + ytm / frequency),
            "dv01": p0 * duration / 10000, "convexity": convexity,
            "yield_basis": f"nominal annual yield, compounded {frequency} times; {terms['day_count']}",
            "price_shocks": [{"yield_change_bps": bps,
                              "price": dirty_price_from_yield(terms, settlement, ytm + bps / 10000),
                              "basis": "illustrative parallel yield shock, not a forecast"}
                             for bps in (-100, -50, 50, 100)]}


def bill_metrics(face: float, dirty: float, settlement: date, maturity: date) -> dict:
    if not all(number(v) is not None and v > 0 for v in (face, dirty)) or settlement >= maturity:
        raise ValueError("Positive bill price/face and future maturity required")
    days = (maturity - settlement).days
    gain = face / dirty - 1
    return {"holding_period_return_pct": gain * 100,
            "simple_annualized_yield_pct": gain * 365 / days * 100,
            "maturity_days": days, "yield_basis": "simple annualized investment yield; ACT/365F; not coupon-bond nominal YTM"}


def budget_lots(budget, dirty_unit_price, lot_size, *, fixed_cost=None, cost_rate=None) -> dict:
    """Illustration only after a separate, centrally assigned budget and costs exist."""
    values = [number(v, nonnegative=True) for v in (budget, dirty_unit_price, lot_size, fixed_cost, cost_rate)]
    if any(v is None for v in values) or values[1] <= 0 or values[2] <= 0 or values[2] != int(values[2]):
        raise ValueError("Known budget, positive unit price/integer lot and explicit nonnegative costs required")
    try:
        budget_d, price, lot, fixed, rate = (Decimal(str(v)) for v in values)
        lots = max(int(((budget_d - fixed) / (price * lot * (1 + rate))).to_integral_value(rounding=ROUND_FLOOR)), 0)
        units = lots * int(lot)
        cost = price * units * (1 + rate) + (fixed if units else 0)
        return {"units": units, "estimated_cost": float(cost), "unspent": float(budget_d - cost)}
    except (InvalidOperation, ArithmeticError) as exc:
        raise ValueError("Budget computation failed") from exc
