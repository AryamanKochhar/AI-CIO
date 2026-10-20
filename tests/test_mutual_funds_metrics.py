"""Independent golden examples for MF return, correlation and XIRR semantics."""
from datetime import date, timedelta
import math

import pytest

from ai_cio.services.mutual_funds.metrics import correlation, investor_xirr, performance, xirr


def _daily(start, end, rate):
    days = (end - start).days
    return [{"date": (start + timedelta(days=i)).isoformat(), "value": 100 * (1 + rate) ** (i / 365.25)}
            for i in range(days + 1) if (start + timedelta(days=i)).weekday() < 5]


def test_growth_benchmark_and_expense_semantics():
    start, end = date(2019, 1, 1), date(2026, 10, 19)
    nav, tri = _daily(start, end, .10), _daily(start, end, .12)
    metrics = performance(nav, tri, as_of=end, passive=True)
    three = next(row for row in metrics["returns"] if row["period"] == "3y")
    assert three["fund_return_pct"] == pytest.approx(10, abs=1e-5)
    assert three["benchmark_return_pct"] == pytest.approx(12, abs=1e-5)
    assert three["excess_return_pp"] == pytest.approx(-2, abs=1e-5)
    assert metrics["rolling"]["observations"] == 36
    assert metrics["rolling"]["outperformance_pct"] == 0
    assert metrics["max_drawdown_pct"] == 0
    assert metrics["tracking_error_pct"] is not None
    assert "not subtracted again" in metrics["method"]


def test_matched_benchmark_dates_use_same_older_end_not_current_nav():
    nav = _daily(date(2018, 1, 1), date(2026, 10, 19), .10)
    tri = _daily(date(2018, 1, 1), date(2026, 9, 30), .12)
    metrics = performance(nav, tri, as_of=date(2026, 10, 20))
    assert all(row["end_date"] == "2026-09-30" for row in metrics["returns"])
    assert metrics["as_of"] == "2026-10-19"


@pytest.mark.parametrize("option,status", [("idcw", "distribution_adjustment_required"), ("unknown", "option_unverified")])
def test_distribution_options_do_not_mislabel_nav_price_as_total_return(option, status):
    nav = [{"date": "2025-01-01", "value": 100}, {"date": "2026-01-01", "value": 90}]
    metrics = performance(nav, as_of=date(2026, 1, 1), option=option)
    assert metrics["status"] == status
    assert metrics["returns"] == []
    assert metrics["volatility_pct"] is None


def test_drawdown_is_peak_to_trough_not_net_change():
    nav = [{"date": "2026-01-01", "value": 100}, {"date": "2026-01-02", "value": 120},
           {"date": "2026-01-05", "value": 90}, {"date": "2026-01-06", "value": 130}]
    metrics = performance(nav, as_of=date(2026, 1, 6))
    assert metrics["max_drawdown_pct"] == -25
    assert metrics["volatility_pct"] is None  # four points do not support annual volatility


def test_no_history_gap_becomes_zero_return_or_fake_cagr():
    nav = [{"date": "2025-01-01", "value": 100}, {"date": "2026-02-01", "value": 120}]
    metrics = performance(nav, as_of=date(2026, 2, 1))
    assert metrics["returns"][0]["fund_return_pct"] is None
    assert metrics["returns"][0]["status"] == "insufficient_history"


def _months(start_year, count, inverse=False):
    import calendar
    value = 100
    points = []
    for index in range(count):
        year, month = start_year + index // 12, index % 12 + 1
        change = (.01 + math.sin(index) * .04) * (-1 if inverse else 1)
        value *= 1 + change
        points.append({"date": date(year, month, calendar.monthrange(year, month)[1]).isoformat(), "value": value})
    return points


def test_correlation_is_aligned_monthly_not_level_correlation():
    a, b = _months(2023, 36), _months(2023, 36, inverse=True)
    result = correlation(a, b, as_of=date(2026, 1, 15))
    assert result["correlation"] == pytest.approx(-1)
    assert result["observations"] == 35
    assert result["frequency"] == "monthly"
    assert result["status"] == "supported"


def test_partial_current_month_and_short_history_do_not_qualify():
    points = _months(2025, 12) + [{"date": "2026-01-15", "value": 130}]
    result = correlation(points, points, as_of=date(2026, 1, 15))
    assert result["observations"] == 11
    assert result["correlation"] is None
    assert result["status"] == "insufficient_history"


def test_zero_variance_does_not_produce_nan():
    points = [{**row, "value": 100} for row in _months(2023, 36)]
    result = correlation(points, points, as_of=date(2026, 1, 15))
    assert result["status"] == "zero_variance"
    assert result["correlation"] is None


def test_investor_xirr_uses_cashflows_not_fund_cagr():
    result = investor_xirr([{"date": "2025-01-01", "amount": 10000, "transaction_type": "purchase"}],
                           valuation=11000, valuation_date="2026-01-01", complete=True)
    assert result["xirr_pct"] == pytest.approx(10, abs=1e-5)
    assert result["status"] == "supported"
    assert xirr([(date(2025, 1, 1), -10000), (date(2025, 7, 2), -10000), (date(2026, 1, 1), 22000)]) != pytest.approx(10)


def test_partial_transactions_and_unknown_transaction_type_withhold_xirr():
    txn = [{"date": "2025-01-01", "amount": 10000, "transaction_type": "purchase"}]
    assert investor_xirr(txn, valuation=11000, valuation_date="2026-01-01", complete=False)["xirr_pct"] is None
    txn[0]["transaction_type"] = "unknown"
    assert investor_xirr(txn, valuation=11000, valuation_date="2026-01-01", complete=True)["status"] == "unclassified_cashflow"


def test_nonconventional_cashflows_with_multiple_xirr_roots_are_withheld():
    # -100 +230/(1+r) -132/(1+r)^2 has roots 10% and 20%.
    assert xirr([(date(2023, 1, 1), -100), (date(2024, 1, 1), 230), (date(2024, 12, 31), -132)]) is None


def test_weekly_nav_is_not_annualized_as_daily_volatility_or_tracking_error():
    start = date(2023, 1, 6)  # Friday observations; >60 samples still are weekly.
    nav = [{"date": (start + timedelta(weeks=i)).isoformat(), "value": 100 * (1.02 ** i) * (1 + .03 * math.sin(i))} for i in range(104)]
    tri = [{**row, "value": row["value"] * (1 + .01 * math.cos(i))} for i, row in enumerate(nav)]
    result = performance(nav, tri, as_of=date(2025, 1, 1), passive=True)
    assert result["volatility_pct"] is None
    assert result["tracking_error_pct"] is None
    assert result["volatility_status"] == "unsupported_observation_cadence"
    assert result["tracking_error_status"] == "unsupported_observation_cadence"
    assert result["risk_window"]["daily_cadence"]["median_calendar_gap_days"] == 7
    assert "Weekly" in result["volatility_note"]
    assert result["max_drawdown_pct"] is not None  # unannualized observed drawdown remains available


def test_weekly_imported_tri_does_not_turn_matched_weekly_returns_into_daily_tracking_error():
    nav = _daily(date(2023, 1, 1), date(2025, 1, 1), .10)
    tri = [dict(row, value=row["value"] * (1 + .01 * math.sin(i))) for i, row in enumerate(nav) if date.fromisoformat(row["date"]).weekday() == 4]
    result = performance(nav, tri, as_of=date(2025, 1, 1), passive=True)
    assert result["volatility_pct"] is not None
    assert result["volatility_status"] == "supported"
    assert result["tracking_error_pct"] is None
    assert result["tracking_error_status"] == "unsupported_observation_cadence"
    assert result["tracking_cadence"]["median_calendar_gap_days"] == 7


def test_normal_weekday_daily_series_preserves_independent_volatility_and_tracking_math():
    from statistics import stdev
    first, last = date(2025, 1, 1), date(2025, 7, 1)
    dates = [first + timedelta(days=i) for i in range((last - first).days + 1) if (first + timedelta(days=i)).weekday() < 5]
    nav, tri, fund_value, index_value = [], [], 100.0, 100.0
    fund_changes, excess_changes = [], []
    for i, when in enumerate(dates):
        if i:
            change, index_change = .01 * math.sin(i), .007 * math.cos(i)
            fund_value *= 1 + change
            index_value *= 1 + index_change
            fund_changes.append(change)
            excess_changes.append(change - index_change)
        nav.append({"date": when.isoformat(), "value": fund_value})
        tri.append({"date": when.isoformat(), "value": index_value})
    result = performance(nav, tri, as_of=last, passive=True)
    assert result["volatility_status"] == result["tracking_error_status"] == "supported"
    assert result["volatility_pct"] == pytest.approx(stdev(fund_changes) * math.sqrt(252) * 100, abs=1e-6)
    assert result["tracking_error_pct"] == pytest.approx(stdev(excess_changes) * math.sqrt(252) * 100, abs=1e-6)
    assert result["risk_window"]["daily_cadence"]["weekday_coverage_pct"] == 100
