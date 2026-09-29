"""Unit tests for Decision Trace builders — no fabricated agent opinions."""
from __future__ import annotations

from ai_cio.services.decision_trace import (
    build_agent_perspectives,
    build_decision_trace,
    build_temporal_changes,
)


def test_agent_perspectives_marks_unevaluated():
    payload = build_agent_perspectives(
        analysis_agent="SimpleAllocatorAnalyzer",
        analysis_focus="general",
        decision="Hold allocation pending more data",
        top_worries=[],
        recommended_actions=[],
        tax_intelligence={"available": False, "status": "skipped"},
        fd_intelligence={"available": False, "status": "disabled"},
        trajectory_intelligence={"available": False, "status": "skipped"},
        sector_opportunity={},
        goal_likelihood=[],
        tradeoffs=[],
        risks=[],
    )
    by_name = {a["agent"]: a for a in payload["agents"]}
    assert by_name["tax_agent"]["status"] == "not_evaluated"
    assert by_name["tax_agent"]["finding"] == "Not evaluated"
    assert by_name["fd_agent"]["status"] == "not_evaluated"
    assert payload["key_disagreement"] is None


def test_disagreement_when_sell_and_tax_caution():
    payload = build_agent_perspectives(
        analysis_agent="EquityAgentAnalyzer",
        analysis_focus="equity",
        decision="Review concentration",
        top_worries=[{"title": "High concentration", "detail": "Top holding 28%", "severity": "high"}],
        recommended_actions=["Trim largest holding to reduce concentration risk"],
        tax_intelligence={
            "available": True,
            "summary": {"stcg": 0, "ltcg": 100000, "estimated_tax": 12500},
            "opportunities": [
                {
                    "label": "Unrealized LTCG on XYZ",
                    "type": "unrealized",
                    "reason": "Selling may create taxable gains",
                    "risks": ["Tax realization"],
                }
            ],
            "comments": [],
            "tax_implications_for_recommendations": [
                {"label": "Recommendation tax caution", "detail": "Review lots"}
            ],
        },
        fd_intelligence={"available": True, "status": "ok", "comments": ["Cash+FD covers 4 months"], "summary": {}},
        trajectory_intelligence={
            "available": True,
            "score": {"overall_score": 62, "max_score": 100, "label": "On track", "explanations": ["OK"]},
            "recommended_actions": [],
        },
        sector_opportunity={"available": True, "recommendations": [{"name": "IT", "logic": "RS up"}]},
        goal_likelihood=[],
        tradeoffs=["Concentration cut vs tax cost"],
        risks=["Single-name risk"],
    )
    assert payload["key_disagreement"] is not None
    assert "tax" in payload["key_disagreement"]["summary"].lower()
    assert "tax_agent" in payload["agents"][0]["conflicts_with"]


def test_temporal_requires_two_snapshots():
    empty = build_temporal_changes({"portfolio": {"snapshots": []}})
    assert empty["available"] is False
    assert empty["items"] == []

    filled = build_temporal_changes(
        {
            "portfolio": {
                "snapshots": [
                    {"month_year": "2024-01", "valuation": 1000000, "change_amount": None, "change_pct": None},
                    {
                        "month_year": "2024-06",
                        "valuation": 1100000,
                        "change_amount": 50000,
                        "change_pct": 4.8,
                    },
                ]
            }
        }
    )
    assert filled["available"] is True
    assert len(filled["items"]) >= 1
    assert filled["items"][0]["metric"] == "Portfolio valuation"


def test_decision_trace_pipeline_shape():
    trace = build_decision_trace(
        decision="Review Financials concentration",
        confidence="medium",
        key_factors=["Largest holding above 15%"],
        rationale=["Financials above threshold"],
        assumptions=["Illustrative returns"],
        risks=["Sector shock"],
        tradeoffs=["Tax vs diversification"],
        recommended_actions=["Review position size"],
        top_worries=[
            {
                "title": "Financials concentration",
                "detail": "22% of equity",
                "severity": "high",
                "metric": "22%",
            }
        ],
        concentration_analysis={"largest_holding_percent": 18},
        true_exposure={"sector_exposure": [{"sector": "Financials", "percent": "22"}]},
        tax_intelligence={"available": False, "status": "skipped"},
        fd_intelligence={"available": False, "status": "skipped"},
        trajectory_intelligence={"available": False, "status": "skipped"},
        sector_opportunity={},
        goal_likelihood=[],
        execution={"stages": ["analyze"], "duration_ms": 12, "analyzer": "SimpleAllocatorAnalyzer"},
        twin={
            "portfolio": {"total_value": {"known": True, "value": 2500000}},
            "financial_position": {"liquid": {"known": True, "value": 300000}},
        },
    )
    assert trace["available"] is True
    assert "chain-of-thought" in (trace["disclaimer"] or "").lower() or "chain-of-thought" in trace["disclaimer"]
    steps = trace["steps"]
    assert steps["inputs"]
    assert steps["observations"]
    assert steps["final_finding"]["decision"] == "Review Financials concentration"
    # Tax not evaluated — finding must not invent tax advice
    tax = next(a for a in steps["specialist_findings"] if a["agent"] == "tax_agent")
    assert tax["status"] == "not_evaluated"
