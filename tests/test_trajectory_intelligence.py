"""Deterministic trajectory: projection, score, behavior, what-if."""
from __future__ import annotations

from decimal import Decimal

from ai_cio.services.trajectory.behavior import analyze_behavior
from ai_cio.services.trajectory.engine import build_financial_snapshot, build_trajectory_intelligence
from ai_cio.services.trajectory.math_utils import fv_annuity, fv_lump, required_pmt
from ai_cio.services.trajectory.projection import apply_what_if, build_projections
from ai_cio.services.trajectory.score import build_trajectory_score


def test_lump_and_annuity_projection():
    lump = fv_lump(Decimal("100000"), Decimal("0.10"), 10)
    assert lump > Decimal("250000")
    sip = fv_annuity(Decimal("10000"), Decimal("0.10"), 10)
    assert sip > Decimal("1000000")
    need = required_pmt(Decimal("500000"), Decimal("0.10"), 10)
    assert need is not None and need > 0


def test_multi_scenario_horizons():
    proj = build_projections(
        principal=Decimal("500000"),
        monthly_contribution=Decimal("20000"),
        horizons=[5, 10, 15, 20],
    )
    assert set(proj["scenarios"].keys()) == {"conservative", "base", "optimistic"}
    assert "20" in proj["endpoints_by_horizon"]
    cons = Decimal(proj["endpoints_by_horizon"]["15"]["conservative"]["value"])
    base = Decimal(proj["endpoints_by_horizon"]["15"]["base"]["value"])
    opt = Decimal(proj["endpoints_by_horizon"]["15"]["optimistic"]["value"])
    assert cons < base < opt
    # contributions vs growth present
    pt = proj["series"]["base"][10]
    assert pt["contributions"] is not None
    assert pt["growth"] is not None


def test_what_if_contribution_delta():
    result = apply_what_if(
        principal=Decimal("300000"),
        base_monthly=Decimal("15000"),
        monthly_override=Decimal("25000"),
        horizon=15,
    )
    assert Decimal(result["projected_value"]) > Decimal(result["base_projected_value"])
    assert Decimal(result["delta_vs_base"]) > 0


def test_score_missing_components_not_zero():
    score = build_trajectory_score(
        snapshot={"savings_rate_percent": None, "liquid_months_cover": None},
        goal_rows=[],
        behavior={"components": {}},
        portfolio_health={},
        tax_summary=None,
    )
    assert score["overall_score"] is None
    assert "savings_rate" in score["missing_data"]
    assert score["component_scores"]["savings_rate"]["status"] == "insufficient_data"
    assert score["component_scores"]["savings_rate"]["score"] is None


def test_score_with_partial_data():
    score = build_trajectory_score(
        snapshot={"savings_rate_percent": "25", "liquid_months_cover": "6"},
        goal_rows=[{"likelihood_percent": 80}],
        behavior={
            "components": {
                "consistency": {"score": 85, "note": "stable"},
            }
        },
        portfolio_health={
            "components": {
                "diversification": {"available": True, "score": 70},
                "risk": {"available": True, "score": 65},
            }
        },
        tax_summary={"data_quality": {"coverage_pct": 80}},
    )
    assert score["overall_score"] is not None
    assert 0 <= score["overall_score"] <= 100
    assert score["component_scores"]["savings_rate"]["score"] is not None


def test_behavior_insufficient_and_consistency():
    empty = analyze_behavior([])
    assert empty["available"] is False
    assert empty["behavior_score"] is None

    txns = []
    for i, month in enumerate(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]):
        txns.append(
            {
                "date": f"{month}-15",
                "transaction_type": "PURCHASE",
                "amount": "10000" if i % 2 == 0 else "10500",
            }
        )
    result = analyze_behavior(
        txns,
        holdings=[{"valuation": "80000"}, {"valuation": "20000"}],
    )
    assert result["available"] is True
    assert result["behavior_score"] is not None
    assert "consistency" in result["components"]
    assert result["source"] == "observed_transactions"


def test_build_trajectory_intelligence_integration():
    twin = {
        "financial_position": {
            "income": {"value": "150000"},
            "expenses": {"value": "80000"},
            "liquid": {"value": "200000"},
            "net_worth": {"value": "1500000"},
            "fixed_deposits": {"total_principal": "100000"},
            "liabilities": {"total_balance": "50000"},
        },
        "portfolio": {
            "total_value": {"value": "1200000"},
            "holdings": [{"valuation": "700000"}, {"valuation": "500000"}],
        },
        "goals": {
            "items": [
                {
                    "id": 1,
                    "name": "Home",
                    "target_amount": "8000000",
                    "current_funding": "500000",
                    "horizon_years": 10,
                }
            ]
        },
        "portfolio_health": {
            "components": {
                "diversification": {"available": True, "score": 72},
                "risk": {"available": True, "score": 68},
            }
        },
    }
    txns = [
        {"date": "2024-01-10", "transaction_type": "BUY", "amount": "20000"},
        {"date": "2024-02-10", "transaction_type": "BUY", "amount": "20000"},
        {"date": "2024-03-10", "transaction_type": "BUY", "amount": "22000"},
        {"date": "2024-04-10", "transaction_type": "SELL", "amount": "5000"},
    ]
    snap = build_financial_snapshot(twin)
    assert snap["monthly_surplus"] == "70000.00"
    assert Decimal(snap["savings_rate_percent"]) > 0

    payload = build_trajectory_intelligence(twin, txns, horizon_years=20)
    assert payload["available"] is True
    assert payload["score"]["overall_score"] is not None
    assert "base" in payload["projections"]["series"]
    assert len(payload["goal_projections"]) == 1
    assert payload["behavior"]["available"] is True
    assert "disclaimer" in payload
