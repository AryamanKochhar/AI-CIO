"""Legacy portfolio views must agree with canonical measured MF evidence."""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date

from ai_cio.services.agents.mutual_fund_agent import run_mutual_fund_agent
from ai_cio.services.mutual_funds.integration import reconcile_portfolio_analysis


def _canonical():
    return {"result_version": "mf-intelligence-v1", "as_of": "2026-10-20",
            "funds": [{"fund_id": key, "identity_status": "verified", "valuation": value, "known_statement_value": value,
                       "disclosure": {"available": True, "stale": False, "observed_on": "2026-09-30"}}
                      for key, value in (("a", 1000), ("b", 2000))],
            "overlaps": [{"fund_a": "a", "fund_b": "b", "status": "partial_coverage", "weighted_overlap_pct": 60,
                          "coverage_a_pct": 80, "coverage_b_pct": 90}],
            "combined_exposure": {"status": "partial", "known_coverage_pct": 85, "portfolio_value": 3500,
                                  "known_value": 2975, "unmapped_value": 525,
                                  "securities": [{"isin": "security", "direct_value": 500, "mf_value": 2475, "total_value": 2975}],
                                  "note": "Disclosed weights applied once to statement values; residual exposure stays unknown."}}


def test_measured_exposure_replaces_blanket_missing_claim_without_inventing_score_or_taxonomy():
    analysis = {"true_exposure": {"market_cap_exposure": [{"category": "Small cap", "percent": "50"}], "sector_exposure": [{"sector": "Banks", "percent": "60"}]},
                "concentration_analysis": {"geographic_concentration": [{"region": "India (assumed)", "percent": "100"}]},
                "top_worries": [{"title": "Fund overlap not measured"}, {"title": "Liquidity buffer", "detail": "Keep this unrelated concern"}],
                "portfolio_health": {"score": 72, "stars": 4, "components": {"risk": {"score": 70, "available": True}, "fund_overlap": {"score": None, "available": False}}},
                "financial_health": {"monthly_income": "100000.00"}, "data_gaps": {"fund_lookthrough": True, "market_cap_classification": True},
                "portfolio_flags": {"high_fund_overlap": False}}
    original = deepcopy(analysis)
    canonical = _canonical()
    canonical_before = deepcopy(canonical)
    reconcile_portfolio_analysis(analysis, canonical)
    assert canonical == canonical_before
    actual = analysis["true_exposure"]["mutual_fund_lookthrough"]
    assert actual["mutual_fund_coverage_pct"] == 82.5  # MF 2475 / 3000, not combined portfolio's 85%
    assert actual["known_coverage_pct"] == 85
    assert actual["mutual_fund_coverage_status"] == "partial"
    overlap = analysis["concentration_analysis"]["fund_overlap"]
    assert overlap["available"] is True and overlap["maximum_weighted_overlap_pct"] == 60
    assert overlap["pair_coverage_pct"] == 100  # pair observed; remaining security coverage is a separate gap
    assert overlap["status"] == "partial"
    assert analysis["data_gaps"]["fund_lookthrough"] is True
    assert analysis["data_gaps"]["fund_overlap"] is True
    assert analysis["data_gaps"]["market_cap_classification"] is True
    assert analysis["portfolio_health"]["score"] == original["portfolio_health"]["score"]
    assert analysis["portfolio_health"]["components"]["fund_overlap"]["score"] is None
    assert analysis["portfolio_health"]["components"]["fund_overlap"]["available"] is True
    assert analysis["portfolio_flags"]["high_fund_overlap"] is True
    assert [r["title"] for r in analysis["top_worries"]] == ["Liquidity buffer"]
    assert analysis["financial_health"]["monthly_income"] == "100000.00"
    assert analysis["true_exposure"]["market_cap_exposure"] == original["true_exposure"]["market_cap_exposure"]
    assert "heuristic" in analysis["true_exposure"]["market_cap_exposure_basis"]
    assert analysis["concentration_analysis"]["geographic_concentration"][0]["underlying_geography_verified"] is False


def test_stale_pairs_do_not_remove_unknown_worry_or_turn_direct_only_coverage_into_mf_lookthrough():
    @dataclass
    class Result:
        true_exposure: dict = field(default_factory=dict)
        concentration_analysis: dict = field(default_factory=dict)
        portfolio_health: dict = field(default_factory=dict)
        top_worries: list = field(default_factory=lambda: [{"title": "Fund overlap not measured"}])
    analysis = Result()
    canonical = _canonical()
    canonical["funds"][0]["disclosure"]["stale"] = True
    canonical["combined_exposure"]["securities"][0].update({"direct_value": 500, "mf_value": 0, "total_value": 500})
    canonical["combined_exposure"]["known_coverage_pct"] = 500 / 3500 * 100
    reconcile_portfolio_analysis(analysis, canonical)
    assert analysis.true_exposure["mutual_fund_lookthrough"]["available"] is False
    assert analysis.true_exposure["mutual_fund_lookthrough"]["mutual_fund_coverage_pct"] == 0
    assert analysis.concentration_analysis["fund_overlap"]["available"] is False
    assert analysis.concentration_analysis["fund_overlap"]["maximum_weighted_overlap_pct"] is None
    assert analysis.top_worries == [{"title": "Fund overlap not measured"}]
    assert analysis.portfolio_health["components"]["fund_overlap"]["score"] is None


def test_disabled_flag_prevents_provider_execution_and_preserves_safe_schema(monkeypatch):
    monkeypatch.setattr("ai_cio.services.agents.mutual_fund_agent.settings.MUTUAL_FUND_AGENT_ENABLED", False)
    class ForbiddenProvider:
        def begin_run(self):
            raise AssertionError("Disabled agent must not execute providers")
    result = run_mutual_fund_agent({}, provider=ForbiddenProvider(), as_of=date(2026, 10, 20))
    assert result["status"] == "disabled"
    assert result["available"] is False
    assert result["result_version"] == "mf-intelligence-v1"
    assert result["combined_exposure"]["known_coverage_pct"] is None
    assert result["funds"] == result["overlaps"] == result["correlations"] == result["findings"] == result["sources"] == []
