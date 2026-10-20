"""Independent numeric fixtures and evidence gates for the Bond specialist."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import csv
import io

import pytest

from ai_cio.services.agents.bond_agent import run_bond_agent
from ai_cio.services.bonds.analysis import quote_state
from ai_cio.services.bonds.cashflows import (
    accrued_interest, bill_metrics, budget_lots, coupon_dates, dirty_price_from_yield,
    fixed_cashflows, full_price, rate_metrics, year_fraction, yield_to_maturity,
)
from ai_cio.services.bonds.provider import DhanBondProvider, classify_row, parse_master, cache_fingerprint
from ai_cio.services.bonds.terms import load_verified_terms


AS_OF = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_analysis_clock(monkeypatch):
    from ai_cio.services.bonds import analysis
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(analysis, "datetime", Clock)


def fixed():
    return {"category": "government_dated", "regular_option_free": True, "cashflows_verified": True,
            "maturity_date": "2028-01-01", "face_value": 100, "coupon_rate_pct": 10,
            "coupon_frequency": 2, "day_count": "30E/360"}


def twin():
    return {"financial_position": {"cashflow_cadence": "monthly", "income": {"known": True, "value": "100000"},
                                   "expenses": {"known": True, "value": "40000"}, "liquid": {"known": True, "value": "300000"}},
            "behaviour": {"status": "known", "scores": {"risk_score": 65, "loss_aversion_score": 60}},
            "goals": {"items": [{"id": 1, "name": "Home repair", "target_date": "2027-12-31"}]},
            "decision_constraints": {"goal_ids": [1]},
            "contribution_policy": {"status": "bounded", "earmarks_confirmed": True, "uncommitted_monthly_ceiling": "20000"},
            "portfolio": {"holdings": []}}


class FixtureProvider:
    def __init__(self, *, quotes=False):
        self.quotes = quotes

    def market_snapshot(self, products, *, as_of):
        now = NOW.isoformat()
        result = {"master": {}, "quotes": {}, "sources": [], "errors": [], "status": "fixture"}
        for p in products:
            result["master"][p["isin"]] = {"category": p["category"], "lot_size": p["lot_size"], "buy_sell_indicator": "A"}
            if self.quotes:
                price = 99 if p["category"] == "treasury_bill" else 101 if p["category"] == "government_dated" else 15000
                result["quotes"][p["isin"]] = {"last_price": price, "last_trade_time": now, "fetched_at": now,
                                               "settlement_date": as_of.isoformat(), "settlement_verified": True,
                                               "depth": {"buy": [{"price": price - 0.01, "quantity": 10000}],
                                                         "sell": [{"price": price + 0.01, "quantity": 10000}]}}
        return result


def test_rbi_two_year_regular_bond_golden_value_and_analytic_duration():
    # Independent textbook discounting equation, four semiannual cashflows.
    y, settlement = 0.09, date(2026, 1, 1)
    expected = sum(amount / 1.045 ** n for n, amount in enumerate([5, 5, 5, 105], 1))
    assert dirty_price_from_yield(fixed(), settlement, y) == pytest.approx(expected, abs=1e-10)
    assert expected == pytest.approx(101.793762848, abs=1e-8)
    assert yield_to_maturity(fixed(), settlement, expected) == pytest.approx(y, abs=1e-11)
    metrics = rate_metrics(fixed(), settlement, expected)
    weighted = sum(n / 2 * amount / 1.045 ** n for n, amount in enumerate([5, 5, 5, 105], 1))
    analytic_modified = weighted / expected / 1.045
    assert metrics["modified_duration"] == pytest.approx(analytic_modified, rel=1e-7)
    assert metrics["dv01"] == pytest.approx(analytic_modified * expected / 10000, rel=1e-7)
    assert metrics["convexity"] > 0
    assert metrics["price_shocks"][0]["price"] > expected > metrics["price_shocks"][-1]["price"]


def test_coupon_date_accrual_and_dirty_price_do_not_double_count_interest():
    terms, settlement = fixed(), date(2026, 4, 1)
    assert accrued_interest(terms, settlement) == pytest.approx(2.5)
    assert full_price(101, "dirty", terms, settlement) == 101
    assert full_price(98.5, "clean", terms, settlement) == 101
    assert accrued_interest(terms, date(2026, 7, 1)) == 0


def test_coupon_schedule_uses_contractual_dates_without_february_drift():
    previous, dates = coupon_dates(date(2028, 8, 31), date(2027, 1, 1))
    assert dates == [date(2027, 2, 28), date(2027, 8, 31), date(2028, 2, 29), date(2028, 8, 31)]
    assert previous == date(2026, 8, 31)
    assert year_fraction(date(2026, 1, 31), date(2026, 2, 28), "30E/360") == 28 / 360


def test_bill_return_is_simple_annualized_not_coupon_ytm():
    metrics = bill_metrics(100, 98, date(2026, 1, 1), date(2026, 4, 2))
    assert metrics["maturity_days"] == 91
    assert metrics["holding_period_return_pct"] == pytest.approx(2 / 98 * 100)
    assert metrics["simple_annualized_yield_pct"] == pytest.approx(2 / 98 * 365 / 91 * 100)
    assert "ytm_pct" not in metrics


@pytest.mark.parametrize("change", [{"category": "sovereign_gold"}, {"regular_option_free": False}, {"cashflows_verified": False}])
def test_unsupported_or_unverified_cashflows_are_not_valued(change):
    terms = {**fixed(), **change}
    with pytest.raises(ValueError):
        fixed_cashflows(terms, date(2026, 1, 1))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True])
def test_yield_refuses_invalid_prices(value):
    with pytest.raises(ValueError):
        yield_to_maturity(fixed(), date(2026, 1, 1), value)


def test_zero_coupon_bond_has_duration_equal_to_maturity_and_negative_yield_is_supported():
    terms = {**fixed(), "coupon_rate_pct": 0}
    settlement = date(2026, 1, 1)
    price = dirty_price_from_yield(terms, settlement, -0.01)
    assert price > 100
    result = rate_metrics(terms, settlement, price)
    assert result["ytm_pct"] == pytest.approx(-1)
    assert result["macaulay_duration"] == pytest.approx(2, rel=1e-7)


def test_lot_budget_rounds_down_includes_costs_and_does_not_assume_unknown_fees_zero():
    result = budget_lots(10000, 99, 100, fixed_cost=50, cost_rate=0.001)
    assert result["units"] == 100
    assert result["estimated_cost"] == pytest.approx(9959.9)
    assert result["unspent"] == pytest.approx(40.1)
    with pytest.raises(ValueError):
        budget_lots(10000, 99, 100)


def test_master_routing_enum_is_separate_from_economic_classification():
    fields = ["EXCH_ID", "SEGMENT", "SECURITY_ID", "ISIN", "INSTRUMENT", "INSTRUMENT_TYPE", "SERIES", "LOT_SIZE"]
    stream = io.StringIO(); writer = csv.DictWriter(stream, fields); writer.writeheader()
    writer.writerow(dict(zip(fields, ["NSE", "E", "10046", "IN0020190065", "EQUITY", "DBT", "GS", "1"])))
    writer.writerow(dict(zip(fields, ["NSE", "E", "10232", "IN0020220045", "EQUITY", "Other", "GB", "1"])))
    rows = parse_master(stream.getvalue())["rows"]
    assert [r["category"] for r in rows] == ["government_dated", "sovereign_gold"]
    assert all(r["instrument"] == "EQUITY" for r in rows)
    assert classify_row({"EXCH_ID": "NSE", "SEGMENT": "E", "INSTRUMENT_TYPE": "ES", "SERIES": "EQ", "SYMBOL_NAME": "CHEMBOND"}) is None


def test_empty_quote_keeps_real_terms_but_never_manufactures_yield_or_units():
    profile = twin(); before = deepcopy(profile)
    result = run_bond_agent(profile, provider=FixtureProvider(), as_of=AS_OF)
    assert result["available"] is True and result["status"] == "terms_only"
    assert len(result["catalogue_products"]) == 3 and result["eligible_products"] == []
    assert all(p["price"] is p["ytm_pct"] is p["units"] is None for p in result["catalogue_products"])
    sources = {s["id"] for s in result["sources"]}
    assert all(set(p["source_ids"]) <= sources for p in result["catalogue_products"])
    assert len([f for f in result["findings"] if f["type"] == "quote_readiness"]) == 1
    assert profile == before


def test_catalogue_sgb_contains_actual_original_coupon_basis_and_no_fixed_redemption():
    result = run_bond_agent(twin(), provider=FixtureProvider(), as_of=AS_OF)
    product = next(p for p in result["catalogue_products"] if p["category"] == "sovereign_gold")
    assert product["face_value"] == 5091
    assert product["terms"]["coupon_per_unit_per_payment"] == pytest.approx(63.6375)
    assert product["terms"]["redemption_value"] is None
    assert product["yield_status"] == "gold_linked_not_fixed_ytm"
    assert "bond_sgb_listing_nse" in product["source_ids"]


def test_fresh_tbill_can_be_comparison_but_shared_ceiling_alone_does_not_allocate_units():
    result = run_bond_agent(twin(), provider=FixtureProvider(quotes=True), as_of=AS_OF)
    bill = next(p for p in result["catalogue_products"] if p["category"] == "treasury_bill")
    assert bill["eligibility_status"] == "eligible_for_comparison"
    assert bill["yield_status"] == "computed_verified_cashflows" and bill["ytm_pct"] is None
    assert bill["metrics"]["simple_annualized_yield_pct"] > 0
    assert bill["units"] is None
    assert not next(p for p in result["catalogue_products"] if p["category"] == "government_dated")["readiness"]["status"] == "ready"


def test_specific_assignment_and_known_costs_create_one_nonadditive_budget_illustration():
    profile = twin(); profile["decision_constraints"].update(bond_allocation_budget=15000, bond_fixed_cost=10, bond_cost_rate=0)
    result = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    bill = next(p for p in result["eligible_products"] if p["category"] == "treasury_bill")
    assert bill["units"] == 100 and bill["estimated_cost"] <= 15000
    assert "alternative" in bill["budget_basis"]
    profile["decision_constraints"]["bond_allocation_budget"] = 30000
    result = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    assert all(p["units"] is None for p in result["catalogue_products"])


def test_actual_psychometric_and_liquidity_inputs_change_product_suitability():
    profile = twin(); profile["decision_constraints"]["allow_gold"] = True
    profile["goals"]["items"][0]["target_date"] = "2035-01-01"
    ready = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    assert len(ready["eligible_products"]) == 3
    profile["behaviour"]["scores"]["loss_aversion_score"] = 20
    cautious = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    assert [p["category"] for p in cautious["eligible_products"]] == ["treasury_bill"]
    profile["financial_position"]["liquid"]["value"] = "0"
    no_reserve = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    assert no_reserve["eligible_products"] == []


def test_multiple_goals_require_joint_selection_before_personalized_ranking():
    profile = twin(); profile["decision_constraints"] = {}
    profile["goals"]["items"].append({"id": 2, "name": "Retirement", "target_date": "2045-01-01"})
    result = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    assert result["eligible_products"] == []
    assert any("Select one goal" in reason for p in result["catalogue_products"] for reason in p["readiness"]["reasons"])


def test_stale_zero_depth_and_future_trades_never_pass_quote_readiness():
    now = NOW; terms = load_verified_terms(as_of=AS_OF)["products"][0]
    base = {"last_price": 100, "last_trade_time": now.isoformat(), "fetched_at": now.isoformat(),
            "depth": {"buy": [{"price": 99.99, "quantity": 1}], "sell": [{"price": 100.01, "quantity": 1}]}}
    assert quote_state(base, terms, now=now, as_of=AS_OF)["quote_status"] == "verified_fresh_depth"
    assert quote_state({**base, "fetched_at": (now - timedelta(minutes=6)).isoformat()}, terms, now=now, as_of=AS_OF)["quote_status"] == "stale"
    assert quote_state({**base, "last_trade_time": (now + timedelta(days=1)).isoformat()}, terms, now=now, as_of=AS_OF)["quote_status"] == "stale"
    assert quote_state({**base, "depth": {}}, terms, now=now, as_of=AS_OF)["quote_status"] == "price_only"


def test_default_provider_does_not_access_network_in_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("BOND_CACHE_DIR", str(tmp_path))
    result = DhanBondProvider().market_snapshot([], as_of=AS_OF)
    assert result["master"] == {} and "disabled in tests" in result["errors"][0]
    before = cache_fingerprint(); (tmp_path / "public.json").write_text('{"public":true}')
    assert cache_fingerprint() != before


def test_terms_verified_after_backtest_date_are_not_used():
    assert load_verified_terms(as_of=date(2026, 1, 1))["products"] == []


def test_past_maturity_is_excluded_even_when_quote_fixture_supplies_data():
    result = run_bond_agent(twin(), provider=FixtureProvider(quotes=True), as_of=date(2026, 12, 11))
    bill = next(p for p in result["catalogue_products"] if p["category"] == "treasury_bill")
    assert bill["eligibility_status"] != "eligible_for_comparison"
    assert any("maturity is on or before" in reason for reason in bill["readiness"]["reasons"])


def test_recorded_horizon_is_applied_as_an_explicitly_derived_anchor():
    profile = twin()
    profile["goals"]["items"][0].pop("target_date")
    profile["goals"]["items"][0]["horizon_years"] = 15
    result = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    goal = result["data_quality"]["goals"][0]
    assert goal["target_date"] is None and goal["comparison_date"] == "2041-10-20"
    assert "Derived planning anchor" in goal["date_basis"]
    assert any(p["category"] == "government_dated" for p in result["eligible_products"])
    assert "illustrative anchor" in result["catalogue_products"][0]["goal_role"]


def test_clean_ask_quantity_uses_same_full_cash_price_as_the_yield(monkeypatch):
    from ai_cio.services.bonds import analysis
    original = load_verified_terms
    def clean_terms(*, as_of):
        payload = original(as_of=as_of)
        payload["products"][0]["price_basis"] = "clean"
        return payload
    monkeypatch.setattr(analysis, "load_verified_terms", clean_terms)
    profile = twin()
    profile["goals"]["items"][0]["target_date"] = "2035-01-01"
    profile["decision_constraints"].update(bond_allocation_budget=204, bond_fixed_cost=0, bond_cost_rate=0)
    result = run_bond_agent(profile, provider=FixtureProvider(quotes=True), as_of=AS_OF)
    bond = next(p for p in result["eligible_products"] if p["category"] == "government_dated")
    assert bond["price"] == 101 and bond["metrics"]["comparison_ask"] == pytest.approx(101.01)
    assert bond["comparison_price"] > 102 and bond["comparison_price_basis"] == "dirty"
    assert bond["units"] == 1  # Two raw clean asks would incorrectly fit this budget.
    assert bond["estimated_cost"] == pytest.approx(bond["comparison_price"])
