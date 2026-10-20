"""Reproducible historical metrics. No LLM numbers or return forecasts."""
from __future__ import annotations

from bisect import bisect_right
import calendar
from datetime import date, timedelta
import math
from statistics import mean, median, stdev

from .disclosures import iso_date, number


def series(points: list[dict]) -> list[tuple[date, float]]:
    values = {}
    for row in points:
        when, value = iso_date(row["date"]), number(row["value"], minimum=0.000000001)
        if when in values and values[when] != value:
            raise ValueError("Conflicting values on one observation date")
        values[when] = value
    return sorted(values.items())


def _round(value, digits=6):
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _year_before(when: date, years: int) -> date:
    return when.replace(year=when.year - years, day=min(when.day, calendar.monthrange(when.year - years, when.month)[1]))


def _at_or_before(values: list[tuple[date, float]], target: date, *, tolerance: int = 10):
    idx = bisect_right([row[0] for row in values], target) - 1
    if idx < 0 or (target - values[idx][0]).days > tolerance:
        return None
    return values[idx]


def _return(start, end, *, annualized: bool) -> float | None:
    days = (end[0] - start[0]).days
    if days <= 0:
        return None
    result = ((end[1] / start[1]) ** (365.25 / days) - 1) * 100 if annualized else (end[1] / start[1] - 1) * 100
    return _round(result)


def _daily_returns(values):
    """Return weekday-close changes only when their observed cadence supports it.

    A seven-calendar-day gap alone cannot establish daily sampling: a weekly
    series also satisfies that bound. Require mostly complete weekday coverage
    AND a median one-calendar-day spacing, separately from the sample-size
    requirement. This is an explicit conservative application eligibility rule,
    not a certification of an exchange holiday calendar.
    """
    weekdays = [(d, v) for d, v in values if d.weekday() < 5]
    gaps = [(b[0] - a[0]).days for a, b in zip(weekdays, weekdays[1:])]
    if weekdays:
        count = (weekdays[-1][0] - weekdays[0][0]).days + 1
        weeks, remainder = divmod(count, 7)
        expected = weeks * 5 + sum((weekdays[0][0].weekday() + i) % 7 < 5 for i in range(remainder))
        coverage = len(weekdays) / expected if expected else 0
    else:
        coverage = 0
    candidates = {b[0]: b[1] / a[1] - 1 for a, b in zip(weekdays, weekdays[1:]) if 0 < (b[0] - a[0]).days <= 7}
    cadence_supported = bool(gaps) and median(gaps) <= 1 and coverage >= .85
    supported = cadence_supported and len(candidates) >= 60
    status = "supported" if supported else "unsupported_observation_cadence" if gaps and not cadence_supported else "insufficient_daily_history"
    reason = ("Observed weekday-close cadence supports the application daily convention; at least 60 returns."
              if supported else "Daily annualization is withheld: observation spacing/weekday coverage does not support daily sampling. Weekly, sparse or irregular series are not scaled by sqrt(252)."
              if status == "unsupported_observation_cadence" else "Daily annualization is withheld until at least 60 supported weekday-close returns exist.")
    receipt = {"status": status, "reason": reason, "frequency": "weekday_daily" if cadence_supported else "unverified",
               "weekday_observations": len(weekdays), "candidate_returns": len(candidates),
               "median_calendar_gap_days": median(gaps) if gaps else None,
               "weekday_coverage_pct": _round(coverage * 100),
               "policy": "Application eligibility: sample weekday closes, median spacing <=1 calendar day, >=85% weekday coverage and >=60 returns; gaps >7 calendar days excluded. Holiday compliance is not independently certified."}
    return candidates if supported else {}, receipt


def monthly_returns(points: list[dict], *, as_of: date) -> dict[date, float]:
    values = series(points)
    months = {}
    for when, value in values:
        month_end = date(when.year, when.month, calendar.monthrange(when.year, when.month)[1])
        if month_end <= as_of and (month_end - when).days <= 7:
            months[month_end] = (when, value)
    result = {}
    rows = sorted(months.items())
    for (a_month, a), (b_month, b) in zip(rows, rows[1:]):
        expected_year, expected_month = (a_month.year + 1, 1) if a_month.month == 12 else (a_month.year, a_month.month + 1)
        if (b_month.year, b_month.month) == (expected_year, expected_month):
            result[b_month] = b[1] / a[1] - 1
    return result


def correlation(a: list[dict], b: list[dict], *, as_of: date) -> dict:
    left, right = monthly_returns(a, as_of=as_of), monthly_returns(b, as_of=as_of)
    dates = sorted(set(left) & set(right))[-60:]
    base = {"correlation": None, "observations": len(dates), "frequency": "monthly",
            "start_date": dates[0].isoformat() if dates else None,
            "end_date": dates[-1].isoformat() if dates else None,
            "status": "insufficient_history", "method": "Pearson correlation of aligned completed-month returns; at least 12 common observations, maximum 60."}
    if len(dates) < 12:
        return base
    xs, ys = [left[x] for x in dates], [right[x] for x in dates]
    mx, my = mean(xs), mean(ys)
    dx, dy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if dx < 1e-24 or dy < 1e-24:
        return {**base, "status": "zero_variance"}
    result = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(dx * dy)
    return {**base, "correlation": _round(max(-1.0, min(1.0, result))),
            "status": "supported" if len(dates) >= 24 else "limited_history"}


def performance(nav_points: list[dict], benchmark_points: list[dict] | None = None,
                *, as_of: date, option: str = "growth", passive: bool = False) -> dict:
    empty = {"returns": [], "volatility_pct": None, "max_drawdown_pct": None,
             "rolling": {"window_years": 1, "observations": 0, "outperformance_pct": None, "median_excess_pp": None},
             "tracking_error_pct": None, "xirr_pct": None, "status": "insufficient_history",
             "volatility_status": "not_evaluated", "volatility_note": "Supported daily NAV sampling is required for the daily annualization convention.",
             "tracking_error_status": "not_evaluated", "tracking_error_note": "Supported matched daily fund/TRI observations are required; a weekly imported index is not daily data.",
             "method": "NAV is net of scheme expenses; TER is not subtracted again. Historical returns are not forecasts."}
    if option != "growth":
        return {**empty, "status": "distribution_adjustment_required" if option == "idcw" else "option_unverified",
                "note": "IDCW or unidentified options need verified distribution/reinvestment adjustments before total-return or return-risk comparison."}
    values = [(d, v) for d, v in series(nav_points) if d <= as_of]
    if len(values) < 2:
        return empty
    benchmark = [(d, v) for d, v in series(benchmark_points or []) if d <= as_of]
    # When a TRI exists, both series use exactly the same common observation
    # dates and end date. This avoids comparing a current fund return against a
    # benchmark ending a month earlier.
    shared = sorted(set(d for d, _ in values) & set(d for d, _ in benchmark))
    bmap, vmap = dict(benchmark), dict(values)
    aligned = [(d, vmap[d]) for d in shared]
    aligned_b = [(d, bmap[d]) for d in shared]
    output = {**empty, "status": "supported", "as_of": values[-1][0].isoformat(),
              "observations": len(values), "inception_observation": values[0][0].isoformat(),
              "benchmark_status": "matched_total_return_series" if len(shared) >= 2 else "unavailable_or_no_common_dates"}
    returns = []
    for years in (1, 3, 5):
        end = values[-1]
        target = _year_before(end[0], years)
        start = _at_or_before(values, target)
        annualized = years > 1
        fund_return = _return(start, end, annualized=annualized) if start else None
        row = {"period": f"{years}y", "fund_return_pct": fund_return, "benchmark_return_pct": None,
               "excess_return_pp": None, "start_date": start[0].isoformat() if start else None,
               "end_date": end[0].isoformat(), "annualized": annualized,
               "status": "supported" if start else "insufficient_history"}
        if aligned:
            shared_end = aligned[-1]
            shared_start = _at_or_before(aligned, _year_before(shared_end[0], years))
            if shared_start:
                d0, d1 = shared_start[0], shared_end[0]
                fund = _return((d0, vmap[d0]), (d1, vmap[d1]), annualized=annualized)
                bench = _return((d0, bmap[d0]), (d1, bmap[d1]), annualized=annualized)
                row.update({"fund_return_pct": fund, "benchmark_return_pct": bench,
                            "excess_return_pp": _round(fund - bench), "start_date": d0.isoformat(),
                            "end_date": d1.isoformat(), "status": "matched_benchmark"})
        returns.append(row)
    output["returns"] = returns
    cutoff = _year_before(values[-1][0], 5)
    risk_values = [(d, v) for d, v in values if d >= cutoff]
    daily_returns, daily_cadence = _daily_returns(risk_values)
    daily = list(daily_returns.values())
    output["volatility_status"] = daily_cadence["status"]
    output["volatility_note"] = daily_cadence["reason"]
    if daily_cadence["status"] == "supported":
        output["volatility_pct"] = _round(stdev(daily) * math.sqrt(252) * 100)
    peak = risk_values[0][1]
    drawdown = 0.0
    for _, value in risk_values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    output["max_drawdown_pct"] = _round(drawdown * 100)
    output["risk_window"] = {"start_date": risk_values[0][0].isoformat(), "end_date": risk_values[-1][0].isoformat(),
                             "daily_observations": len(daily), "daily_cadence": daily_cadence,
                             "volatility_convention": "Sample standard deviation of eligible weekday-close changes x sqrt(252); minimum 60. Unsupported cadence is withheld, not imputed daily."}
    if aligned:
        ends = {}
        for d, v in aligned:
            last = date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
            if last <= as_of and (last - d).days <= 7:
                ends[last] = (d, v)
        rolling = []
        for _, end in sorted(ends.items())[-36:]:
            start = _at_or_before(aligned, _year_before(end[0], 1))
            if start:
                d0, d1 = start[0], end[0]
                fund = (vmap[d1] / vmap[d0] - 1) * 100
                bench = (bmap[d1] / bmap[d0] - 1) * 100
                rolling.append(fund - bench)
        count = len(rolling)
        output["rolling"] = {"window_years": 1, "observations": count,
                             "outperformance_pct": _round(sum(x > 0 for x in rolling) / count * 100) if count else None,
                             "median_excess_pp": _round(median(rolling)) if count else None,
                             "status": "supported" if count >= 12 else "limited_history",
                             "method": "One-year absolute returns ending on matched completed-month observations, last 36 windows; overlapping windows are not independent trials."}
        if passive:
            fund_daily, tracking_cadence = _daily_returns(aligned)
            benchmark_daily, _ = _daily_returns(aligned_b)
            output["tracking_error_status"] = tracking_cadence["status"]
            output["tracking_error_note"] = tracking_cadence["reason"]
            output["tracking_cadence"] = tracking_cadence
            gaps = [fund_daily[d] - benchmark_daily[d] for d in sorted(set(fund_daily) & set(benchmark_daily))]
            if tracking_cadence["status"] == "supported" and len(gaps) >= 60:
                output["tracking_error_pct"] = _round(stdev(gaps) * math.sqrt(252) * 100)
                output["tracking_observations"] = len(gaps)
    return output


def xirr(cashflows: list[tuple[date, float]]) -> float | None:
    """Annual money-weighted return, or None if no unique supported root exists."""
    by_date = {}
    for when, amount in cashflows:
        when = iso_date(when)
        amount = number(amount)
        by_date[when] = by_date.get(when, 0) + amount
    flows = sorted((d, v) for d, v in by_date.items() if abs(v) > 1e-9)
    if len(flows) < 2 or flows[0][0] == flows[-1][0] or not any(v < 0 for _, v in flows) or not any(v > 0 for _, v in flows):
        return None
    first = flows[0][0]
    times = [((d - first).days / 365.0, v) for d, v in flows]
    def npv_log(log_rate):
        terms = [-t * log_rate for t, _ in times]
        shift = max(terms)
        return sum(v * math.exp(exponent - shift) for (_, v), exponent in zip(times, terms))
    # Log-rate bracketing covers -99.9999% to +1,000,000%; no Newton initial
    # guess silently selects one root from a nonconventional cashflow series.
    low, high = math.log(0.000001), math.log(10001)
    brackets = []
    previous, previous_value = low, npv_log(low)
    for i in range(1, 257):
        current = low + (high - low) * i / 256
        value = npv_log(current)
        if previous_value == 0:
            brackets.append((previous, previous))
        elif value == 0 or (value < 0) != (previous_value < 0):
            brackets.append((previous, current))
        previous, previous_value = current, value
    if len(brackets) != 1:
        return None
    left, right = brackets[0]
    left_value = npv_log(left)
    for _ in range(100):
        middle = (left + right) / 2
        value = npv_log(middle)
        if abs(value) < 1e-10:
            left = right = middle
            break
        if (value < 0) == (left_value < 0):
            left, left_value = middle, value
        else:
            right = middle
    return _round(math.expm1((left + right) / 2) * 100)


def investor_xirr(transactions: list[dict], *, valuation: float | None, valuation_date: str | None,
                  complete: bool) -> dict:
    base = {"xirr_pct": None, "status": "incomplete_cashflows",
            "note": "Investor XIRR needs complete inception/opening cashflows, dated contributions and withdrawals, and a same-scope terminal valuation; it is separate from fund NAV return."}
    if not complete or valuation is None or not valuation_date or not transactions:
        return base
    terminal_date = iso_date(valuation_date)
    flows = []
    for txn in transactions:
        kind = str(txn.get("transaction_type") or "").lower().replace("-", "_").replace(" ", "_")
        try:
            when, amount = iso_date(txn.get("date")), abs(number(txn.get("amount")))
        except ValueError:
            return base
        if when > terminal_date:
            return {**base, "status": "valuation_predates_cashflows"}
        if kind in {"purchase", "sip", "switch_in", "switchin", "reinvestment", "dividend_reinvestment"}:
            # A reinvested dividend is NOT external investor cashflow. Without
            # distributions marked explicitly, no investor return is guessed.
            if kind in {"reinvestment", "dividend_reinvestment"}:
                continue
            flows.append((when, -amount))
        elif kind in {"redemption", "switch_out", "switchout", "dividend", "idcw", "payout"}:
            flows.append((when, amount))
        elif amount:
            return {**base, "status": "unclassified_cashflow"}
    flows.append((terminal_date, number(valuation, minimum=0)))
    result = xirr(flows)
    return {"xirr_pct": result, "status": "supported" if result is not None else "no_unique_supported_root",
            "cashflow_count": len(flows), "terminal_date": terminal_date.isoformat(),
            "note": "Annual money-weighted return using actual dated external cashflows and terminal valuation; historical, not a forecast."}
