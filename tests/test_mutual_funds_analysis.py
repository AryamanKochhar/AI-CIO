"""Whole-Twin MF analytics with independent portfolio exposure examples."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json

import pytest

from ai_cio.services.agents.mutual_fund_agent import run_mutual_fund_agent
from ai_cio.services.mutual_funds.provider import plan_option

TODAY = date(2026, 10, 20)
A, B = "INF879O01027", "INF879O01100"
X, Y, Z = "INE040A01034", "INE090A01021", "INE009A01021"


def _history(rate):
    first, last = date(2019, 1, 1), date(2026, 10, 19)
    return [{"date": (first + timedelta(days=i)).isoformat(), "value": 100 * (1 + rate) ** (i / 365.25)}
            for i in range((last - first).days + 1) if (first + timedelta(days=i)).weekday() < 5]


class EvidenceProvider:
    def __init__(self, *, stale=False, benchmark=True, coverage=100):
        self.stale, self.has_benchmark, self.coverage = stale, benchmark, coverage
        self.nav_a, self.nav_b, self.tri = _history(.08), _history(.14), _history(.10)

    def resolve(self, holding):
        isin = holding.get("isin")
        plan, option = plan_option(holding.get("scheme_name", ""))
        return {"isin": isin, "identity_status": "verified" if isin in {A, B} else "unresolved", "scheme_code": 122639 if isin == A else 147481 if isin == B else None,
                "scheme_name": holding.get("scheme_name", "Unknown fund"), "plan": plan, "option": option,
                "identity_reason": "Exact test ISIN identity" if isin in {A, B} else "Exact ISIN missing"}

    def history(self, identity, *, as_of):
        return {"points": self.nav_a if identity["isin"] == A else self.nav_b, "meta": {"scheme_category": "Equity Scheme - Small Cap Fund"},
                "source_url": "https://api.mfapi.in/mf/" + str(identity["scheme_code"]), "retrieved_at": "2026-10-20T00:00:00Z", "history_available": True}

    def disclosure(self, identity, *, as_of):
        weights = [(X, 60), (Y, 30), (Z, 10)] if identity["isin"] == A else [(X, 40), (Y, 30), (Z, 30)]
        return {"observed_on": "2026-06-30" if self.stale else "2026-09-30", "source_url": "https://amc.ppfas.com/test.xlsx", "coverage_pct": self.coverage,
                "holdings": [{"isin": isin, "name": isin, "weight_pct": weight * self.coverage / 100, "asset_class": "equity"} for isin, weight in weights],
                "benchmark_id": "NIFTY500TRI", "benchmark_name": "Nifty 500 TRI", "benchmark_source_url": "https://www.niftyindices.com/test",
                "sha256": "a" * 64, "provenance": "user_supplied_source_document", "ter_percent": .5}

    def benchmark(self, benchmark_id, *, as_of):
        return {"benchmark_id": benchmark_id, "name": "Nifty 500 TRI", "kind": "TRI", "source_url": "https://www.niftyindices.com/test",
                "observed_on": "2026-10-19", "points": self.tri, "sha256": "b" * 64} if self.has_benchmark else None


def _twin():
    return {"user": {"id": 1}, "portfolio": {"holdings": [
        {"isin": A, "scheme_name": "Fund A Direct Growth", "valuation": Decimal("1000"), "valuation_date": "2026-09-30", "folio": "a"},
        {"isin": B, "scheme_name": "Fund B Direct Growth", "valuation": "2000", "valuation_date": "2026-09-30", "folio": "b"},
        {"isin": X, "scheme_name": "Direct Bank", "valuation": "500", "asset_class": "equity"}], "transactions_complete": False},
        "financial_position": {"cashflow_cadence": "monthly", "income": {"value": "100000", "known": True}, "expenses": {"value": "70000", "known": True}},
        "decision_constraints": {"monthly_investment_budget": 40000},
        "behaviour": {"status": "known", "scores": {"risk_score": 70, "loss_aversion_score": 30, "recency_bias_score": 20}, "source": "psychometric_assessment"},
        "goals": {"items": [{"id": 2, "name": "Near term", "horizon_years": 2}]}}


def test_known_weighted_overlap_and_direct_plus_indirect_exposure_count_once():
    twin = _twin()
    before = deepcopy(twin)
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert twin == before
    overlap = result["overlaps"][0]
    assert overlap["weighted_overlap_pct"] == 80  # min(60,40)+min(30,30)+min(10,30)
    assert overlap["status"] == "supported"
    x = next(row for row in result["combined_exposure"]["securities"] if row["isin"] == X)
    assert x["direct_value"] == 500
    assert x["mf_value"] == 1400  # .60*1000 + .40*2000
    assert x["total_value"] == 1900
    assert result["combined_exposure"]["portfolio_value"] == 3500
    assert sum(row["total_value"] for row in result["combined_exposure"]["securities"]) == 3500
    assert result["combined_exposure"]["known_coverage_pct"] == 100
    assert not any(row["isin"] in {A, B} for row in result["combined_exposure"]["securities"])


def test_explicit_direct_bonds_are_not_resolved_as_funds_and_stay_in_exposure_denominator():
    from ai_cio.services.mutual_funds.analysis import DIRECT_BOND_ASSET_CLASSES, _groups
    twin = _twin()
    twin["portfolio"]["holdings"].append({"isin": "IN0020230077", "scheme_name": "Direct sovereign bond",
                                           "asset_class": "government_bond", "valuation": "500"})
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert len(result["funds"]) == 2
    assert result["combined_exposure"]["portfolio_value"] == 4000
    assert result["combined_exposure"]["unmapped_value"] == 500
    for asset_class in DIRECT_BOND_ASSET_CLASSES:
        assert _groups([{"asset_class": asset_class, "valuation": 1}]) == []
    assert len(_groups([{"asset_class": "debt", "scheme_name": "Unknown debt mutual fund", "valuation": 1}])) == 1


def test_partial_disclosure_is_lower_bound_not_renormalized_and_missing_is_not_zero():
    result = run_mutual_fund_agent(_twin(), provider=EvidenceProvider(coverage=50), as_of=TODAY)
    assert result["overlaps"][0]["weighted_overlap_pct"] == 40
    assert result["overlaps"][0]["status"] == "partial_coverage"
    assert result["combined_exposure"]["known_value"] == 2000  # 500 direct + .5*(1000+2000)
    assert result["combined_exposure"]["unmapped_value"] == 1500
    assert result["combined_exposure"]["known_coverage_pct"] == pytest.approx(2000 / 3500 * 100, abs=1e-5)


def test_stale_disclosures_do_not_support_current_overlap_or_lookthrough():
    result = run_mutual_fund_agent(_twin(), provider=EvidenceProvider(stale=True), as_of=TODAY)
    assert result["overlaps"][0]["weighted_overlap_pct"] is None
    assert result["overlaps"][0]["status"] == "stale_disclosure"
    assert result["combined_exposure"]["unmapped_value"] == 3000
    assert result["combined_exposure"]["known_value"] == 500
    assert result["funds"][0]["metrics"]["returns"][0]["fund_return_pct"] is not None


def test_actual_psychometric_scores_budget_and_goals_affect_distinct_review_actions():
    result = run_mutual_fund_agent(_twin(), provider=EvidenceProvider(), as_of=TODAY)
    quality = result["data_quality"]
    assert quality["psychometrics"]["effective_risk_score"] == 30
    assert quality["psychometrics"]["implementation_controls"][0]["status"] == "applied"
    assert quality["budget"]["declared_monthly_budget"] == 40000
    assert quality["budget"]["positive_monthly_surplus"] == 30000
    assert quality["budget"]["consent_and_capacity_ceiling"] == 30000
    assert quality["budget"]["available_for_new_mf_contribution"] is None
    types = {f["type"] for f in result["findings"]}
    assert {"psychometric_suitability", "goal_horizon_review", "overlap_review", "persistent_underperformance", "persistent_outperformance"} <= types
    weaker = next(f for f in result["findings"] if f["type"] == "persistent_underperformance")
    stronger = next(f for f in result["findings"] if f["type"] == "persistent_outperformance")
    assert weaker["fund_id"] == A and stronger["fund_id"] == B
    assert "automatic" not in weaker["suggested_action"].lower()
    assert weaker["principle_ids"] == ["mf_persistence", "mf_benchmark", "mf_tax_scope"]


def test_no_benchmark_does_not_prevent_growth_or_invent_relative_judgment():
    result = run_mutual_fund_agent(_twin(), provider=EvidenceProvider(benchmark=False), as_of=TODAY)
    assert result["funds"][0]["metrics"]["returns"][0]["fund_return_pct"] is not None
    assert all(row["benchmark_return_pct"] is None for fund in result["funds"] for row in fund["metrics"]["returns"])
    assert not any(f["type"] in {"persistent_underperformance", "persistent_outperformance"} for f in result["findings"])
    assert result["status"] == "partial"


def test_exact_same_scheme_folios_aggregate_but_return_distinct_plan_options_do_not():
    twin = _twin()
    twin["portfolio"]["holdings"].insert(1, {**twin["portfolio"]["holdings"][0], "folio": "second", "valuation": 500})
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert len(result["funds"]) == 2
    assert result["funds"][0]["valuation"] == 1500
    assert result["funds"][0]["folio_count"] == 2


def test_unknown_value_is_not_zero_and_partial_known_value_is_conserved():
    twin = _twin()
    twin["portfolio"]["holdings"].insert(1, {**twin["portfolio"]["holdings"][0], "folio": "unknown", "valuation": None})
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert result["funds"][0]["valuation"] is None
    assert result["combined_exposure"]["holdings_with_unknown_valuation"] == 1
    assert result["combined_exposure"]["status"] == "partial"
    assert result["combined_exposure"]["known_value"] + result["combined_exposure"]["unmapped_value"] == 3500


def test_unresolved_persona_placeholder_is_visible_and_finite_json_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR", str(tmp_path))
    twin = _twin()
    twin["portfolio"]["holdings"] = [{"scheme_name": "Illustrative debt fund bucket", "valuation": "10000"}]
    result = run_mutual_fund_agent(twin, as_of=TODAY)
    assert result["available"] is True
    assert result["funds"][0]["identity_status"] == "unresolved"
    assert result["combined_exposure"]["unmapped_value"] == 10000
    assert result["combined_exposure"]["known_coverage_pct"] == 0  # known zero covered; not zero portfolio risk
    assert result["funds"][0]["metrics"]["max_drawdown_pct"] is None
    json.dumps(result, allow_nan=False)


def test_provider_failure_is_scoped_to_its_fund_and_no_fund_is_silently_dropped():
    class FailingProvider(EvidenceProvider):
        def history(self, identity, *, as_of):
            if identity["isin"] == A:
                raise ValueError("bad external document")
            return super().history(identity, as_of=as_of)
    result = run_mutual_fund_agent(_twin(), provider=FailingProvider(), as_of=TODAY)
    assert len(result["funds"]) == 2
    assert result["funds"][0]["identity_status"] == "unresolved"
    assert result["funds"][1]["identity_status"] == "verified"
    assert result["combined_exposure"]["unmapped_value"] == 1000


def test_no_holdings_means_unavailable_not_healthy():
    result = run_mutual_fund_agent({"portfolio": {"holdings": []}}, provider=EvidenceProvider(), as_of=TODAY)
    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["combined_exposure"]["known_coverage_pct"] is None


def test_idcw_correlation_and_total_return_are_not_reported_without_distributions():
    twin = _twin()
    twin["portfolio"]["holdings"][0]["scheme_name"] = "Fund A Direct IDCW"
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert result["funds"][0]["metrics"]["status"] == "distribution_adjustment_required"
    assert result["correlations"][0]["correlation"] is None
    assert not any(f["fund_id"] == A and f["type"] == "persistent_underperformance" for f in result["findings"])


def test_unknown_willingness_does_not_convert_income_surplus_into_consent():
    twin = _twin()
    twin.pop("decision_constraints")
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert result["data_quality"]["budget"]["positive_monthly_surplus"] == 30000
    assert result["data_quality"]["budget"]["consent_and_capacity_ceiling"] is None
    assert result["data_quality"]["budget"]["available_for_new_mf_contribution"] is None


def test_amc_reported_tables_do_not_manufacture_computed_benchmark_history_or_rolling():
    class PublishedProvider(EvidenceProvider):
        def published_comparison(self, identity, *, as_of):
            return {"available": True, "source_id": "reported:" + identity["isin"], "basis": "amc_published_reported",
                    "source_url": "https://amc.ppfas.com/factsheet", "observed_on": "2026-09-30", "sha256": "c" * 64,
                    "option_basis": "not_stated_in_published_table", "stale": False,
                    "benchmark": {"id": "NIFTY500TRI", "name": "Nifty 500 TRI", "kind": "TRI", "source_url": "https://amc.ppfas.com/factsheet"},
                    "returns": [{"period": "1y", "fund_return_pct": 999, "benchmark_return_pct": 998, "start_date": None}], "limitations": ["Reported context only"]}
    result = run_mutual_fund_agent(_twin(), provider=PublishedProvider(benchmark=False), as_of=TODAY)
    fund = result["funds"][0]
    assert fund["published_comparison"]["returns"][0]["fund_return_pct"] == 999
    assert fund["metrics"]["returns"][0]["fund_return_pct"] != 999
    assert fund["benchmark_history"] == []
    assert fund["benchmark"]["available"] is False
    assert fund["metrics"]["rolling"]["observations"] == 0
    assert any(f["type"] == "published_performance_context" for f in result["findings"])
    assert not any(f["type"] in {"persistent_underperformance", "persistent_outperformance"} for f in result["findings"])


def test_default_test_mode_never_opens_unmocked_network_even_for_valid_isin(monkeypatch, tmp_path):
    monkeypatch.setenv("AICIO_TESTING", "1")
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR", str(tmp_path))
    opened = []
    def forbidden_client(*args, **kwargs):
        opened.append(True)
        raise AssertionError("Unexpected network")
    monkeypatch.setattr("ai_cio.services.mutual_funds.provider.httpx.Client", forbidden_client)
    result = run_mutual_fund_agent(_twin(), as_of=TODAY)
    assert opened == []
    assert len(result["funds"]) == 2
    assert all(f["identity_status"] == "unresolved" for f in result["funds"])


def test_unknown_cashflow_cadence_does_not_become_monthly_capacity():
    twin = _twin()
    twin["financial_position"].pop("cashflow_cadence")
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    assert result["data_quality"]["budget"]["declared_monthly_budget"] == 40000
    assert result["data_quality"]["budget"]["positive_monthly_surplus"] is None
    assert result["data_quality"]["budget"]["consent_and_capacity_ceiling"] is None


def test_central_shared_budget_receipt_is_used_without_allocating_it_again_to_mf():
    twin = _twin()
    twin["contribution_policy"] = {"declared_monthly_budget": "20000.00", "monthly_surplus": "30000.00",
                                   "total_monthly_ceiling": "20000.00", "other_goal_commitments": "8000.00",
                                   "reserve_commitment": "2000.00", "uncommitted_monthly_ceiling": "10000.00",
                                   "earmarks_confirmed": True, "status": "bounded", "scope": "One shared budget."}
    result = run_mutual_fund_agent(twin, provider=EvidenceProvider(), as_of=TODAY)
    budget = result["data_quality"]["budget"]
    assert budget["source"] == "central_orchestration"
    assert budget["declared_monthly_budget"] == 20000  # not standalone constraints' 40000
    assert budget["consent_and_capacity_ceiling"] == 20000
    assert budget["other_goal_monthly_commitments"] == 8000
    assert budget["uncommitted_shared_monthly_ceiling"] == 10000
    assert budget["available_for_new_mf_contribution"] is None
    assert budget["status"] == "bounded"
