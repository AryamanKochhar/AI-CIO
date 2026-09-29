"""Counterfactual / what-if builders — deterministic only."""
from __future__ import annotations

from decimal import Decimal

from ai_cio.services.counterfactuals import build_counterfactuals


def test_builds_scenarios_for_aryaman_like_twin():
    twin = {
        "portfolio": {
            "total_value": {"known": True, "value": "1257065.12"},
            "snapshots": [
                {"month_year": "2025-06", "valuation": "1194889.57"},
                {"month_year": "2025-11", "valuation": "1263279.29"},
            ],
        },
        "financial_position": {"liquid": {"known": True, "value": "420000.00"}},
    }
    tax = {
        "available": True,
        "summary": {"stcg": "351.17", "estimated_tax": "70.23"},
        "opportunities": [
            {
                "type": "tax_loss_harvesting",
                "security": "HDFC BANK",
                "amount": "40871.88",
                "estimated_tax_impact": "70.23",
                "reason": "TLH candidate",
                "confidence": 0.35,
                "risks": ["Wash-sale not modelled"],
            }
        ],
    }
    traj = {
        "available": True,
        "snapshot": {
            "monthly_surplus": "30000.00",
            "monthly_expenses": "70000.00",
        },
    }
    conc = {"largest_holding_percent": "25.23"}
    out = build_counterfactuals(
        twin=twin,
        tax_intelligence=tax,
        trajectory_intelligence=traj,
        concentration_analysis=conc,
    )
    assert out["available"] is True
    ids = {s["id"] for s in out["scenarios"]}
    assert "trim_vs_hold_largest" in ids
    assert "contribution_forward" in ids
    assert "return_assumptions" in ids
    assert "snapshot_path_divergence" in ids
    assert "tlh_vs_hold" in ids
    trim = next(s for s in out["scenarios"] if s["id"] == "trim_vs_hold_largest")
    assert trim["actual"]["label"] == "HOLD"
    assert Decimal(trim["deltas"]["cash_freed"]) > 0


def test_empty_when_no_data():
    out = build_counterfactuals(twin={})
    assert out["available"] is False
    assert out["scenarios"] == []
