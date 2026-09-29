"""AI narrative layer over deterministic counterfactuals.

Numbers stay rule-based. The LLM only explains, ranks, and frames trade-offs.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_cio import settings

logger = logging.getLogger(__name__)


def _short(text: Any, limit: int = 140) -> str:
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


def _scenario_brief(scenario: dict[str, Any]) -> dict[str, Any]:
    actual = scenario.get("actual") or {}
    alts = scenario.get("alternatives") or []
    return {
        "id": scenario.get("id"),
        "kind": scenario.get("kind"),
        "title": scenario.get("title"),
        "question": _short(scenario.get("question"), 180),
        "actual_label": actual.get("label"),
        "actual_summary": _short(actual.get("summary"), 120),
        "deltas": scenario.get("deltas") or {},
        "alternatives": [
            {
                "label": a.get("label"),
                "summary": _short(a.get("summary"), 120),
                "projected_value": a.get("projected_value"),
                "delta_vs_base": a.get("delta_vs_base"),
                "cash_freed": a.get("cash_freed"),
                "largest_holding_percent": a.get("largest_holding_percent"),
            }
            for a in alts[:3]
            if isinstance(a, dict)
        ],
        "assumptions": (scenario.get("assumptions") or [])[:3],
        "confidence": scenario.get("confidence"),
    }


def enrich_counterfactuals_with_ai(
    payload: dict[str, Any],
    *,
    twin: dict[str, Any] | None = None,
    decision: str | None = None,
    top_worries: list[dict[str, Any]] | None = None,
    recommended_actions: list[str] | None = None,
    behavioural: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach AI narrative fields without mutating deterministic numbers."""
    out = dict(payload or {})
    if not out.get("available") or not out.get("scenarios"):
        out["ai"] = {"used": False, "reason": "No deterministic scenarios to narrate."}
        return out

    if not settings.equity_llm_configured():
        out["ai"] = {
            "used": False,
            "reason": "LLM not configured — showing deterministic scenarios only.",
        }
        return out

    try:
        narrative = _ask_llm(
            scenarios=[_scenario_brief(s) for s in out["scenarios"]],
            twin=twin or {},
            decision=decision,
            top_worries=top_worries or [],
            recommended_actions=recommended_actions or [],
            behavioural=behavioural or {},
        )
    except Exception as exc:
        logger.warning("counterfactual_ai_failed err=%s", exc)
        out["ai"] = {
            "used": False,
            "error": "AI narrative unavailable; deterministic scenarios still shown.",
            "reason": str(exc)[:200],
        }
        return out

    # Merge per-scenario explanations by id — never overwrite numbers
    by_id = {row.get("id"): row for row in (narrative.get("scenarios") or []) if isinstance(row, dict)}
    merged_scenarios: list[dict[str, Any]] = []
    for scenario in out["scenarios"]:
        row = dict(scenario)
        ai_row = by_id.get(scenario.get("id")) or {}
        if ai_row.get("explanation"):
            row["ai_explanation"] = str(ai_row["explanation"])
        if ai_row.get("why_it_matters"):
            row["ai_why_it_matters"] = str(ai_row["why_it_matters"])
        if ai_row.get("priority_rank") is not None:
            try:
                row["ai_priority_rank"] = int(ai_row["priority_rank"])
            except (TypeError, ValueError):
                pass
        merged_scenarios.append(row)

    # Optional reorder by AI priority when ranks present
    if any(s.get("ai_priority_rank") is not None for s in merged_scenarios):
        merged_scenarios.sort(key=lambda s: s.get("ai_priority_rank") if s.get("ai_priority_rank") is not None else 99)

    out["scenarios"] = merged_scenarios
    out["ai"] = {
        "used": True,
        "cio_narrative": narrative.get("cio_narrative"),
        "priority_focus": narrative.get("priority_focus"),
        "tradeoff_insight": narrative.get("tradeoff_insight"),
        "suggested_next_review": narrative.get("suggested_next_review"),
        "model_note": (
            "AI explained and ranked rule-based scenarios. It did not recompute portfolio maths or invent holdings."
        ),
    }
    return out


def _ask_llm(
    *,
    scenarios: list[dict[str, Any]],
    twin: dict[str, Any],
    decision: str | None,
    top_worries: list[dict[str, Any]],
    recommended_actions: list[str],
    behavioural: dict[str, Any],
) -> dict[str, Any]:
    from ai_cio.services.agents.openrouter_client import chat_completion, extract_json_object

    beh = twin.get("behaviour") if isinstance(twin.get("behaviour"), dict) else {}
    scores = beh.get("scores") if isinstance(beh.get("scores"), dict) else {}
    divergences = (behavioural.get("divergences") or []) if isinstance(behavioural, dict) else []

    system = (
        "You are the AI-CIO narrator for counterfactual (what-if) analysis in Indian personal finance. "
        "All numbers in the user JSON are already computed by deterministic engines — treat them as facts. "
        "NEVER invent new rupee amounts, percentages, tax figures, or holdings. "
        "NEVER give buy/sell orders. Educational review language only. "
        "Reply with ONE JSON object only. No markdown. "
        "Schema: {"
        '"cio_narrative":"2-4 sentences synthesizing what matters across scenarios",'
        '"priority_focus":"which scenario id to study first and why (no new numbers)",'
        '"tradeoff_insight":"one clear trade-off sentence",'
        '"suggested_next_review":"one concrete review action for the user (not a trade)",'
        '"scenarios":[{"id":"must match input id","priority_rank":1,'
        '"explanation":"<=45 words tying THIS scenario to the user context",'
        '"why_it_matters":"<=25 words"}]'
        "}"
    )
    user = {
        "decision_summary": decision,
        "psychometric_risk_score": scores.get("risk_score"),
        "behaviour_divergences": [
            {"title": d.get("title"), "summary": _short(d.get("summary"), 120)}
            for d in divergences[:2]
            if isinstance(d, dict)
        ],
        "top_worries": [
            {"title": w.get("title"), "severity": w.get("severity"), "detail": _short(w.get("detail"), 100)}
            for w in top_worries[:4]
            if isinstance(w, dict)
        ],
        "recommended_actions": recommended_actions[:4],
        "deterministic_scenarios": scenarios,
    }
    raw = chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, default=str)},
        ],
        temperature=0.25,
        max_tokens=1800,
        timeout=90.0,
    )
    data = extract_json_object(raw)
    if not isinstance(data, dict):
        raise RuntimeError("AI returned non-object JSON")
    return data
