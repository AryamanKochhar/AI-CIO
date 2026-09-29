"""AI profile-impact layer over portfolio news + Digital Twin.

News headlines and Twin facts are inputs. The LLM explains how news may affect
the user's profile for review — never inventing holdings, weights, or trade orders.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_cio import settings

logger = logging.getLogger(__name__)


def _short(text: Any, limit: int = 160) -> str:
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


def _twin_snapshot(twin: dict[str, Any], news_holdings: list[dict[str, Any]]) -> dict[str, Any]:
    beh = twin.get("behaviour") if isinstance(twin.get("behaviour"), dict) else {}
    scores = beh.get("scores") if isinstance(beh.get("scores"), dict) else {}
    goals = (twin.get("goals") or {}).get("items") if isinstance(twin.get("goals"), dict) else twin.get("goals")
    if not isinstance(goals, list):
        goals = []
    fin = twin.get("financial_position") if isinstance(twin.get("financial_position"), dict) else {}
    pa = twin.get("preanalysis") if isinstance(twin.get("preanalysis"), dict) else {}
    conc = pa.get("concentration") if isinstance(pa.get("concentration"), dict) else {}
    flags = pa.get("portfolio_flags") if isinstance(pa.get("portfolio_flags"), dict) else {}
    health = pa.get("financial_health") if isinstance(pa.get("financial_health"), dict) else {}
    sectors = pa.get("sector_allocation") if isinstance(pa.get("sector_allocation"), list) else []

    return {
        "completeness": twin.get("completeness"),
        "behaviour": {
            "status": beh.get("status"),
            "risk_score": scores.get("risk_score"),
            "loss_aversion_score": scores.get("loss_aversion_score"),
            "risk_capacity_score": scores.get("risk_capacity_score"),
        },
        "goals": [
            {
                "name": g.get("name") or g.get("title"),
                "target_date": g.get("target_date"),
                "target_amount": g.get("target_amount"),
            }
            for g in goals[:4]
            if isinstance(g, dict)
        ],
        "financial_position": {
            "liquid": fin.get("liquid"),
            "monthly_income": fin.get("monthly_income"),
            "monthly_expenses": fin.get("monthly_expenses"),
        },
        "portfolio_signals": {
            "largest_holding_percent": conc.get("largest_holding_percent"),
            "high_single_holding_concentration": flags.get("high_single_holding_concentration"),
            "emergency_months_cover": health.get("emergency_months_cover"),
            "debt_to_income": health.get("debt_to_income"),
        },
        "top_sectors": [
            {"sector": row.get("sector") or row.get("label"), "weight_percent": row.get("weight_percent")}
            for row in sectors[:4]
            if isinstance(row, dict)
        ],
        "news_holdings": news_holdings[:5],
    }


def enrich_news_with_profile_impact(
    payload: dict[str, Any],
    *,
    twin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach AI profile-impact narrative; does not mutate news articles."""
    out = dict(payload or {})
    articles = out.get("articles") or []
    holdings = out.get("holdings") or []

    if not articles:
        out["profile_impact"] = {
            "used": False,
            "reason": out.get("reason") or "No news articles to analyze against your profile.",
        }
        return out

    if not settings.equity_llm_configured():
        out["profile_impact"] = {
            "used": False,
            "reason": "LLM not configured — showing news feed only.",
        }
        return out

    try:
        narrative = _ask_llm(
            articles=[
                {
                    "holding": a.get("holding"),
                    "title": _short(a.get("title"), 200),
                    "description": _short(a.get("description"), 240),
                    "source": a.get("source"),
                    "published_at": a.get("published_at"),
                }
                for a in articles[:8]
                if isinstance(a, dict)
            ],
            twin_snapshot=_twin_snapshot(twin or {}, holdings),
        )
    except Exception as exc:
        logger.warning("news_ai_failed err=%s", exc)
        out["profile_impact"] = {
            "used": False,
            "error": "Profile impact analysis unavailable; news articles still shown.",
            "reason": str(exc)[:200],
        }
        return out

    out["profile_impact"] = {
        "used": True,
        "summary": narrative.get("profile_impact_summary"),
        "urgency": narrative.get("urgency"),
        "profile_areas": narrative.get("profile_areas") or [],
        "holding_impacts": narrative.get("holding_impacts") or [],
        "suggested_profile_reviews": narrative.get("suggested_profile_updates") or [],
        "model_note": (
            "AI interpreted news against your Twin profile. It did not invent holdings, "
            "weights, or prices, and does not place trades."
        ),
    }
    return out


def _ask_llm(
    *,
    articles: list[dict[str, Any]],
    twin_snapshot: dict[str, Any],
) -> dict[str, Any]:
    from ai_cio.services.agents.openrouter_client import chat_completion, extract_json_object

    system = (
        "You are the AI-CIO news analyst for Indian personal finance. "
        "Given recent news headlines and a Digital Twin snapshot, explain how the news may "
        "affect the user's financial PROFILE for review — concentration, goals fit, liquidity, "
        "behaviour alignment, and what to re-check on their Twin. "
        "Use ONLY facts from the JSON inputs. NEVER invent rupee amounts, percentages, "
        "holdings, or price moves not stated in the news. "
        "NEVER give buy/sell/hold orders. Use educational review language only. "
        "Reply with ONE JSON object only. No markdown. "
        "Schema: {"
        '"profile_impact_summary":"2-4 sentences on how this news relates to THIS user profile",'
        '"urgency":"watch|monitor|no_material_change",'
        '"profile_areas":[{"area":"concentration|goals|liquidity|behaviour|risk",'
        '"impact":"<=40 words","review_note":"<=30 words — profile review, not a trade"}],'
        '"holding_impacts":[{"holding":"must match a news holding name",'
        '"news_context":"<=35 words from headlines only",'
        '"profile_effect":"<=40 words tying to Twin signals",'
        '"suggested_review":"<=30 words — update Twin assumptions or monitor, not trade"}],'
        '"suggested_profile_updates":["2-4 concrete profile review actions, not trades"]'
        "}"
    )
    user = {
        "twin_snapshot": twin_snapshot,
        "news_articles": articles,
    }
    raw = chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, default=str)},
        ],
        temperature=0.25,
        max_tokens=1600,
        timeout=90.0,
    )
    data = extract_json_object(raw)
    if not isinstance(data, dict):
        raise RuntimeError("AI returned non-object JSON")
    return data
