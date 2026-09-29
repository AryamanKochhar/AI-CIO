"""AI enrichment over counterfactuals — skips cleanly when LLM off."""
from __future__ import annotations

from ai_cio.services.counterfactual_ai import enrich_counterfactuals_with_ai


def test_enrich_skips_when_no_llm(monkeypatch):
    monkeypatch.setattr("ai_cio.services.counterfactual_ai.settings.equity_llm_configured", lambda: False)
    payload = {
        "available": True,
        "scenarios": [
            {
                "id": "trim_vs_hold_largest",
                "title": "Trim vs hold",
                "actual": {"label": "HOLD"},
                "alternatives": [{"label": "TRIM"}],
                "deltas": {"cash_freed": "1000.00"},
            }
        ],
    }
    out = enrich_counterfactuals_with_ai(payload, decision="Review concentration")
    assert out["ai"]["used"] is False
    assert out["scenarios"][0]["deltas"]["cash_freed"] == "1000.00"
    assert "ai_explanation" not in out["scenarios"][0]


def test_enrich_merges_narrative_without_changing_numbers(monkeypatch):
    monkeypatch.setattr("ai_cio.services.counterfactual_ai.settings.equity_llm_configured", lambda: True)

    def fake_ask(**kwargs):
        return {
            "cio_narrative": "Concentration and tax trade off.",
            "priority_focus": "Start with trim_vs_hold_largest.",
            "tradeoff_insight": "Risk cut vs tax realization.",
            "suggested_next_review": "Review largest holding size against emergency goal.",
            "scenarios": [
                {
                    "id": "trim_vs_hold_largest",
                    "priority_rank": 1,
                    "explanation": "Largest weight conflicts with moderate risk score.",
                    "why_it_matters": "Primary concentration lever.",
                }
            ],
        }

    monkeypatch.setattr("ai_cio.services.counterfactual_ai._ask_llm", fake_ask)
    payload = {
        "available": True,
        "scenarios": [
            {
                "id": "trim_vs_hold_largest",
                "title": "Trim vs hold",
                "actual": {"label": "HOLD"},
                "alternatives": [{"label": "TRIM"}],
                "deltas": {"cash_freed": "50000.00"},
            }
        ],
    }
    out = enrich_counterfactuals_with_ai(payload, decision="Review")
    assert out["ai"]["used"] is True
    assert out["ai"]["cio_narrative"].startswith("Concentration")
    assert out["scenarios"][0]["ai_priority_rank"] == 1
    assert out["scenarios"][0]["deltas"]["cash_freed"] == "50000.00"
