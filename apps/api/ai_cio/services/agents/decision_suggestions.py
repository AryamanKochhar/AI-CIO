"""Select distinct, skill-cited reviews rather than filling a list with prose."""
from __future__ import annotations

from typing import Any

from ai_cio.services.grounded_reviews import build_grounded_reviews
from ai_cio.services.suggestion_ranking import rank_suggestions


def build_decision_suggestions(*, twin: dict[str, Any], analysis_bits: dict[str, Any],
                             sector_opportunity: dict[str, Any], goal_likelihood: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reviewed = build_grounded_reviews(twin, analysis_bits)
    items = rank_suggestions(reviewed["items"])
    return {
        "available": bool(items), "summary": reviewed["summary"], "items": items,
        "coverage": reviewed["coverage"], "explanation_version": "applied-principles-v1",
        "ranking": {
            "version": "review-priority-v2",
            "method": "Distinct causal themes are selected first (at most one exposure review). Explicit conditional application-triage scores order up to eight supported findings; no filler minimum. Relative support = this card's policy score / the sum for the selected list.",
            "interpretation": "Relative review priority, not a probability of profit or goal success. Skills support the reasoning; they do not prescribe these policy scores or prove future outcomes.",
        },
        "ai_used": False,
        "disclaimer": "Review facts, assumptions and applicable records before taking action. Exact skill citations and arithmetic support a conditional review, not a trade instruction or financial-outcome guarantee.",
    }
