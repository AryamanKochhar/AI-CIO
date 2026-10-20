"""Agent-boundary guards apply to snapshot workers and standalone API callers."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ai_cio.services.agents import tax_agent
from ai_cio.services.tax.engine import build_tax_intelligence

EQUITY_ISIN = "INE009A01021"
FUND_ISIN = "INF879O01027"


def direct_holding():
    return {"isin": EQUITY_ISIN, "scheme_name": "Synthetic Direct Equity", "amc": "EQUITY",
            "asset_class": "equity", "closing_units": "5", "nav": "120", "valuation": "600"}


def transactions(isin=EQUITY_ISIN, amc="EQUITY"):
    return [{"isin": isin, "scheme_name": "Synthetic Security", "amc": amc, "date": "2025-05-01",
             "transaction_type": "PURCHASE", "units": "10", "amount": "1000", "nav": "100"},
            {"isin": isin, "scheme_name": "Synthetic Security", "amc": amc, "date": "2026-02-01",
             "transaction_type": "SELL", "units": "5", "amount": "600", "nav": "120"}]


def fund_holding(name="Synthetic Debt Liquid Arbitrage Growth Fund"):
    return {"isin": FUND_ISIN, "scheme_name": name, "amc": "Synthetic AMC", "asset_class": "mutual_fund",
            "closing_units": "5", "nav": "120", "valuation": "600"}


def run(holdings, txns, monkeypatch, *, snapshot=True):
    monkeypatch.setattr(tax_agent.settings, "TAX_INTELLIGENCE_ENABLED", True)
    if snapshot:
        caller = SimpleNamespace(decision_snapshot=True, holdings=holdings, transactions=txns)
    else:
        caller = SimpleNamespace()
        monkeypatch.setattr(tax_agent.portfolio_svc, "list_holdings", lambda db, uid: holdings)
        monkeypatch.setattr(tax_agent.portfolio_svc, "list_transactions", lambda db, uid: txns)
    return tax_agent.run_tax_agent(caller, 101, financial_year="2025-26")


@pytest.mark.parametrize("snapshot", [True, False])
@pytest.mark.parametrize("name", ["Synthetic Equity Growth Fund", "Synthetic Debt Fund", "Synthetic Arbitrage Fund"])
def test_mf_only_never_enters_legacy_special_rate_totals_or_becomes_zero_tax(monkeypatch, snapshot, name):
    result = run([fund_holding(name)], transactions(FUND_ISIN, "Synthetic AMC"), monkeypatch, snapshot=snapshot)
    assert result["available"] is False
    assert result["status"] == "not_evaluated"
    assert result["summary"].get("estimated_tax") is None
    assert result["summary"].get("stcg") is None
    assert result["tax_estimate"].get("estimated_capital_gains_tax") is None
    assert result["opportunities"] == []
    assert result["tax_lots"] == {"realized": [], "unrealized": []}
    assert result["missing_data"]
    assert all(row["estimated_tax"] is None for row in result["missing_data"])
    assert "unknown, not zero" in result["reason"]
    assert result["calculation_scope"]["whole_portfolio_tax_estimated"] is False


def test_legacy_engine_receives_only_type_verified_direct_equity(monkeypatch):
    seen = []
    def engine(holdings, txns, **kwargs):
        seen.append((holdings, txns))
        return build_tax_intelligence(holdings, txns, **kwargs)
    monkeypatch.setattr(tax_agent, "build_tax_intelligence", engine)
    original_h = [direct_holding(), fund_holding()]
    original_t = transactions() + transactions(FUND_ISIN, "Synthetic AMC")
    before = deepcopy((original_h, original_t))
    result = run(original_h, original_t, monkeypatch)
    assert len(seen) == 1
    h, t = seen[0]
    assert [row["isin"] for row in h] == [EQUITY_ISIN]
    assert {row["isin"] for row in t} == {EQUITY_ISIN}
    assert result["status"] == "partial"
    assert result["available"] is True
    assert result["summary"]["stcg"] == "100.00"
    assert all(row["isin"] == EQUITY_ISIN for row in result["tax_lots"]["realized"])
    assert result["data_quality"]["coverage_pct"] <= 50
    assert result["comments"][0].startswith("Numeric tax estimates cover only")
    assert result["alerts"][0]["type"] == "tax_scope_exclusions"
    assert (original_h, original_t) == before


def test_direct_equity_numeric_engine_calculation_is_preserved(monkeypatch):
    holdings, txns = [direct_holding()], transactions()
    expected = build_tax_intelligence(holdings, txns, financial_year="2025-26")
    result = run(holdings, txns, monkeypatch)
    assert result["summary"] == expected["summary"]
    assert result["tax_estimate"] == expected["tax_estimate"]
    assert result["tax_lots"] == expected["tax_lots"]
    assert result["status"] == expected["status"]
    assert result["calculation_scope"]["excluded_records"] == 0


@pytest.mark.parametrize("asset", ["corporate_bond", "government_bond", "gsec", "t_bill", "treasury_bill", "sovereign_gold_bond", "sgb", "sdl", "fixed_income"])
def test_explicit_debt_class_cannot_enter_equity_tax_via_broker_routing_label(monkeypatch, asset):
    holding = {**direct_holding(), "asset_class": asset, "amc": "EQUITY"}
    result = run([holding], transactions(), monkeypatch)
    assert result["available"] is False
    assert result["summary"].get("estimated_tax") is None
    assert result["calculation_scope"]["supported_transactions"] == 0


@pytest.mark.parametrize("holding", [
    {"scheme_name": "Ambiguous Growth", "isin": EQUITY_ISIN},
    {"scheme_name": "Unidentified equity", "asset_class": "equity", "amc": "EQUITY"},
    {"scheme_name": "Fund incorrectly labelled equity", "asset_class": "equity", "amc": "EQUITY", "isin": FUND_ISIN},
    {"scheme_name": "Foreign equity outside configured Indian scope", "asset_class": "equity", "isin": "US0378331005"},
])
def test_ambiguous_or_unsupported_identity_is_not_defaulted_to_equity(monkeypatch, holding):
    result = run([holding], [], monkeypatch)
    assert result["available"] is False
    assert result["summary"] == {}
    assert result["missing_data"][0]["reason"] == "unsupported_or_unverified_mf_tax_classification"


def test_conflicting_identity_markers_exclude_the_entire_security(monkeypatch):
    contradictory = {**direct_holding(), "asset_class": "mutual_fund", "amc": "Synthetic AMC"}
    result = run([direct_holding(), contradictory], transactions(), monkeypatch)
    assert result["available"] is False
    assert result["calculation_scope"]["supported_transactions"] == 0


def test_transaction_only_closed_direct_equity_can_still_be_calculated(monkeypatch):
    result = run([], transactions(), monkeypatch)
    assert result["available"] is True
    assert result["summary"]["stcg"] == "100.00"
    assert result["calculation_scope"]["supported_transactions"] == 2


def test_missing_fund_lots_and_self_declared_classification_do_not_unlock_tax(monkeypatch):
    fund = {**fund_holding(), "tax_classification": {"verified": True, "category": "equity_oriented_mf"}}
    result = run([fund], [], monkeypatch)
    assert result["available"] is False
    assert result["summary"].get("estimated_tax") is None
    assert "Complete acquisition and disposal lots" in result["missing_data"][0]["required"]


def test_partial_scope_never_turns_unknown_exemption_pool_into_gain_harvest_cta(monkeypatch):
    def engine(*args, **kwargs):
        return {"available": True, "status": "success", "summary": {"estimated_tax": "12.00"},
                "opportunities": [{"type": "gain_harvesting", "threshold_remaining": "125000"}], "data_quality": {}}
    monkeypatch.setattr(tax_agent, "build_tax_intelligence", engine)
    result = run([direct_holding(), fund_holding()], [], monkeypatch)
    assert result["opportunities"] == []
    assert result["summary"]["estimated_tax"] == "12.00"
    assert result["calculation_scope"]["whole_portfolio_exemption_headroom_verified"] is False


def test_decision_tax_impact_names_subset_and_preserves_exclusions(monkeypatch):
    result = run([direct_holding(), fund_holding()], transactions(), monkeypatch)
    row = tax_agent.tax_impact_for_actions(result)[0]
    assert row["label"] == "TAX IMPACT (supported direct-equity subset)"
    assert "not a whole-portfolio tax liability" in row["note"]
    mf_only = run([fund_holding()], [], monkeypatch)
    assert "missing_data" in tax_agent.tax_impact_for_actions(mf_only)[0]
