"""Tests for news profile-impact AI layer."""
from __future__ import annotations

from unittest.mock import patch

from ai_cio.services.news_ai import enrich_news_with_profile_impact


def test_profile_impact_skipped_without_articles():
    payload = {"available": False, "articles": [], "holdings": []}
    out = enrich_news_with_profile_impact(payload, twin={})
    assert out["profile_impact"]["used"] is False


def test_profile_impact_skipped_without_llm():
    payload = {
        "available": True,
        "articles": [{"holding": "Reliance", "title": "Earnings update", "description": "..."}],
        "holdings": [{"name": "Reliance", "valuation": "100000"}],
    }
    with patch("ai_cio.settings.equity_llm_configured", return_value=False):
        out = enrich_news_with_profile_impact(payload, twin={"behaviour": {"scores": {}}})
    assert out["profile_impact"]["used"] is False
    assert "LLM not configured" in out["profile_impact"]["reason"]


def test_profile_impact_merges_ai_narrative():
    payload = {
        "available": True,
        "articles": [
            {
                "holding": "Reliance",
                "title": "Reliance reports quarterly results",
                "description": "Results beat estimates.",
                "source": "Example News",
            }
        ],
        "holdings": [{"name": "Reliance", "valuation": "250000", "asset_class": "equity"}],
    }
    twin = {
        "behaviour": {"scores": {"risk_score": 55}},
        "preanalysis": {"concentration": {"largest_holding_percent": 18}},
    }
    ai_response = {
        "profile_impact_summary": "Reliance headlines matter because it is a large holding.",
        "urgency": "watch",
        "profile_areas": [
            {"area": "concentration", "impact": "News on largest name increases sleeve sensitivity.", "review_note": "Re-check concentration on Twin."}
        ],
        "holding_impacts": [
            {
                "holding": "Reliance",
                "news_context": "Quarterly results headline.",
                "profile_effect": "Large weight means profile volatility exposure rises.",
                "suggested_review": "Review goal timeline assumptions, not trade.",
            }
        ],
        "suggested_profile_updates": ["Confirm Twin concentration still reflects CAS."],
    }
    with patch("ai_cio.settings.equity_llm_configured", return_value=True):
        with patch("ai_cio.services.news_ai._ask_llm", return_value=ai_response):
            out = enrich_news_with_profile_impact(payload, twin=twin)
    assert out["profile_impact"]["used"] is True
    assert out["profile_impact"]["urgency"] == "watch"
    assert out["profile_impact"]["holding_impacts"][0]["holding"] == "Reliance"
    assert out["articles"][0]["title"].startswith("Reliance")
