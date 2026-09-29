"""Blended AI + rule suggestions for Decisions results.

Educational observations only — not buy/sell instructions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_cio import settings
from ai_cio.services.sector_opportunity import rule_based_suggestions

logger = logging.getLogger(__name__)


def _short(text: Any, limit: int = 160) -> str:
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


def build_decision_suggestions(
    *,
    twin: dict[str, Any],
    analysis_bits: dict[str, Any],
    sector_opportunity: dict[str, Any],
    goal_likelihood: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rules = rule_based_suggestions(sector_opportunity, analysis_bits)
    ai_items: list[dict[str, str]] = []
    ai_summary = None
    ai_error = None

    if settings.equity_llm_configured():
        try:
            ai_items, ai_summary = _ask_openrouter(
                twin=twin,
                analysis_bits=analysis_bits,
                sector_opportunity=sector_opportunity,
                goal_likelihood=goal_likelihood or [],
            )
        except Exception as exc:
            # Keep logs detailed; UI gets a short non-technical note when rules still work.
            logger.warning("decision_suggestions_ai_failed err=%s", exc)
            if rules:
                ai_error = "AI narrative skipped (invalid model JSON); showing rule-based suggestions."
            else:
                ai_error = "AI narrative unavailable; no rule-based suggestions either."

    merged: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for item in ai_items + rules:
        title = (item.get("title") or "").strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        merged.append(
            {
                "title": item.get("title") or "Suggestion",
                "detail": item.get("detail") or "",
                "kind": item.get("kind") or "general",
                "source": item.get("source") or "blended",
                "basis": item.get("basis") or "",
            }
        )
        if len(merged) >= 8:
            break

    return {
        "available": bool(merged),
        "summary": ai_summary
        or (
            "Suggestions combine rule-based sector opportunity scores with your Twin concentration profile."
        ),
        "items": merged,
        "ai_used": bool(ai_items),
        "ai_error": ai_error,
        "disclaimer": (
            "Suggestions are educational observations for review — not investment advice "
            "and not an instruction to buy or sell any security."
        ),
    }


def _ask_openrouter(
    *,
    twin: dict[str, Any],
    analysis_bits: dict[str, Any],
    sector_opportunity: dict[str, Any],
    goal_likelihood: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], str | None]:
    from ai_cio.services.agents.openrouter_client import chat_completion, extract_json_object

    health = analysis_bits.get("portfolio_health") or {}
    worries = analysis_bits.get("top_worries") or []
    recs = sector_opportunity.get("recommendations") or []
    deprior = sector_opportunity.get("deprioritized") or []
    goals_brief = [
        {
            "name": g.get("goal_name"),
            "status": g.get("likelihood_status"),
            "coverage": g.get("coverage_ratio"),
        }
        for g in goal_likelihood[:5]
    ]

    system = (
        "You are an educational research assistant for an Indian personal finance CIO tool. "
        "You do NOT give buy/sell orders or product pitches. "
        "Reply with ONE compact JSON object only. No markdown. No trailing commas. "
        "Use straight double quotes. Escape any quotes inside strings. "
        "Schema: "
        '{"summary":"string","suggestions":[{"title":"string","detail":"string","kind":"sector|diversification|risk|goals|general","basis":"string"}]} '
        "Max 4 suggestions. Each detail <= 40 words. Use the provided RULE-BASED sector ranks as facts — do not invent rankings."
    )
    user = {
        "portfolio_health_score": health.get("score"),
        "top_worries": [
            {
                "title": _short(w.get("title"), 80),
                "detail": _short(w.get("detail"), 120),
                "severity": w.get("severity"),
            }
            for w in worries[:3]
        ],
        "rule_based_sector_recommendations": [
            {
                "rank": r.get("rank"),
                "name": r.get("name"),
                "final_score": r.get("final_score"),
                "logic": _short(r.get("logic"), 140),
                "exposure_pct": r.get("exposure_pct"),
            }
            for r in recs[:3]
        ],
        "deprioritized_high_exposure": [
            {"name": d.get("name"), "exposure_pct": d.get("exposure_pct")} for d in deprior[:3]
        ],
        "goal_likelihood": goals_brief,
        "twin_ready": bool((twin or {}).get("ready_for_analysis")),
    }
    raw = chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, default=str)},
        ],
        temperature=0.15,
        max_tokens=1200,
        timeout=90.0,
    )
    data = extract_json_object(raw)
    suggestions_raw = data.get("suggestions") or data.get("items") or []
    items: list[dict[str, str]] = []
    for s in suggestions_raw:
        if not isinstance(s, dict):
            continue
        items.append(
            {
                "title": str(s.get("title") or "Suggestion"),
                "detail": str(s.get("detail") or ""),
                "kind": str(s.get("kind") or "general"),
                "source": "ai",
                "basis": str(s.get("basis") or "AI narrative over rule-based facts"),
            }
        )
    if not items:
        raise RuntimeError("AI returned JSON without usable suggestions")
    summary = data.get("summary")
    return items, str(summary) if summary else None
