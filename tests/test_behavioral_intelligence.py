"""Tests for declared vs observed behavioural intelligence."""
from __future__ import annotations

from ai_cio.services.behavioral_intelligence import build_behavioral_intelligence


def test_not_evaluated_when_empty():
    out = build_behavioral_intelligence(twin={}, observed_behavior=None)
    assert out["declared"]["available"] is False
    assert out["declared"]["items"][0]["value"] == "Not evaluated"
    assert out["observed"]["items"][0]["value"] == "Not evaluated"
    assert out["divergences"] == []


def test_divergence_moderate_risk_high_concentration():
    out = build_behavioral_intelligence(
        twin={
            "behaviour": {
                "status": "known",
                "source": "psychometric_assessment",
                "scores": {"risk_score": 45, "loss_aversion_score": 60},
                "observations": ["Comfortable with moderate volatility."],
            }
        },
        observed_behavior={
            "available": True,
            "status": "ok",
            "behavior_score": 55,
            "source": "observed_transactions",
            "comments": ["Portfolio has become concentrated in a relatively large single holding (observed)."],
            "components": {
                "concentration_discipline": {
                    "score": 40,
                    "largest_holding_percent": "32.00",
                    "note": "Largest holding ~32%",
                }
            },
            "metrics": {"sell_to_buy_ratio": "0.20"},
        },
        concentration_analysis={"largest_holding_percent": 32},
    )
    assert out["available"] is True
    assert out["declared"]["available"] is True
    assert out["observed"]["available"] is True
    assert len(out["divergences"]) >= 1
    assert out["divergences"][0]["causation_claimed"] is False
    assert "concentration" in out["divergences"][0]["summary"].lower()
