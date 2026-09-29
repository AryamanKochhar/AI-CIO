"""Evaluation harness: synthetic financial profiles → expected *detection* of issues.

Does NOT hard-code expected CIO recommendations into production.
"""
from __future__ import annotations

from ai_cio.services.behavioral_intelligence import build_behavioral_intelligence
from ai_cio.services.data_quality import build_data_quality_report
from ai_cio.services.decision_trace import build_agent_perspectives, build_decision_trace


PROFILES = {
    "high_equity_concentration": {
        "top_worries": [
            {
                "title": "Single-stock concentration",
                "detail": "Largest holding 38%",
                "severity": "high",
                "metric": "38%",
            }
        ],
        "recommended_actions": ["Trim largest holding to reduce concentration risk"],
        "concentration": {"largest_holding_percent": 38},
        "expect_worry": True,
        "expect_disagreement_if_tax": True,
    },
    "high_capital_gains": {
        "tax": {
            "available": True,
            "summary": {"stcg": 0, "ltcg": 500000, "estimated_tax": 62500},
            "opportunities": [
                {
                    "label": "Large unrealized LTCG",
                    "reason": "Selling may create taxable gains",
                    "risks": ["Tax realization"],
                }
            ],
            "comments": [],
            "tax_implications_for_recommendations": [
                {"label": "Recommendation tax caution", "detail": "Review lots"}
            ],
            "data_quality": {"usable_cost_lots": 5, "insufficient": 0},
        },
        "recommended_actions": ["Trim largest holding to reduce concentration risk"],
        "expect_tax_finding": True,
        "expect_disagreement": True,
    },
    "incomplete_twin": {
        "twin": {
            "completeness": {
                "psychometric": False,
                "income": False,
                "expenses": False,
                "liquid": False,
                "goals": False,
                "portfolio": True,
                "horizon": False,
            }
        },
        "expect_incomplete": True,
    },
    "stated_vs_observed_risk": {
        "twin": {
            "behaviour": {
                "status": "known",
                "scores": {"risk_score": 42},
                "observations": [],
            }
        },
        "observed": {
            "available": True,
            "comments": ["Concentrated holding observed."],
            "components": {
                "concentration_discipline": {"largest_holding_percent": "30.00", "score": 40}
            },
            "metrics": {},
        },
        "expect_divergence": True,
    },
}


def test_profile_high_concentration_surfaces_in_trace():
    p = PROFILES["high_equity_concentration"]
    trace = build_decision_trace(
        decision="Review concentration",
        confidence="medium",
        key_factors=["Largest holding elevated"],
        rationale=["Concentration above threshold"],
        assumptions=[],
        risks=["Idiosyncratic risk"],
        tradeoffs=[],
        recommended_actions=p["recommended_actions"],
        top_worries=p["top_worries"],
        concentration_analysis=p["concentration"],
        true_exposure={},
        tax_intelligence={"available": False, "status": "skipped"},
        fd_intelligence={"available": False, "status": "skipped"},
        trajectory_intelligence={"available": False, "status": "skipped"},
        sector_opportunity={},
        goal_likelihood=[],
        execution={"stages": ["analyze"], "analyzer": "eval"},
        twin={},
    )
    assert any("concentration" in (o.get("title") or "").lower() for o in trace["steps"]["observations"])


def test_profile_tax_vs_trim_disagreement():
    p = PROFILES["high_capital_gains"]
    views = build_agent_perspectives(
        analysis_agent="eval",
        analysis_focus="equity",
        decision="Review concentration",
        top_worries=[{"title": "Concentration", "detail": "High", "severity": "high"}],
        recommended_actions=p["recommended_actions"],
        tax_intelligence=p["tax"],
        fd_intelligence={"available": False, "status": "skipped"},
        trajectory_intelligence={"available": False, "status": "skipped"},
        sector_opportunity={},
        goal_likelihood=[],
        tradeoffs=[],
        risks=[],
    )
    assert views["key_disagreement"] is not None
    tax = next(a for a in views["agents"] if a["agent"] == "tax_agent")
    assert tax["status"] == "available"
    assert tax["finding"] != "Not evaluated"


def test_profile_incomplete_twin_data_quality():
    p = PROFILES["incomplete_twin"]
    dq = build_data_quality_report(twin=p["twin"], tax_intelligence={"status": "skipped"})
    assert dq["counts"]["incomplete"] >= 3


def test_profile_behaviour_divergence():
    p = PROFILES["stated_vs_observed_risk"]
    out = build_behavioral_intelligence(
        twin=p["twin"],
        observed_behavior=p["observed"],
        concentration_analysis={"largest_holding_percent": 30},
    )
    assert len(out["divergences"]) >= 1
    assert out["divergences"][0]["causation_claimed"] is False
