"""Select distinct, skill-cited reviews rather than filling a list with prose."""
from __future__ import annotations

from typing import Any

from ai_cio.services.grounded_reviews import build_grounded_reviews
from ai_cio.services.suggestion_ranking import rank_suggestions


# Coverage tasks stay inspectable without crowding out measured portfolio facts.
# These IDs describe missing inputs, not an independently established trade case.
_COVERAGE_REVIEWS = {"establish-inputs", "goal-inputs", "cost-disclosures", "mf-evidence-coverage"}
MAX_PRIMARY_REVIEWS = 4


def focus_reviews(reviews: list[dict], *, objective: str = "") -> tuple[list[dict], list[dict]]:
    supported = [row for row in reviews if row.get("id") not in _COVERAGE_REVIEWS]
    selected = supported[:MAX_PRIMARY_REVIEWS]
    if objective in {"review_mutual_fund_portfolio", "review_bond_portfolio"}:
        prefix = "mf_" if objective == "review_mutual_fund_portfolio" else "bond_"
        fund_reviews = [row for row in supported if str(row.get("theme", "")).startswith(prefix)]
        if fund_reviews and not any(row in selected for row in fund_reviews):
            selected = selected[:MAX_PRIMARY_REVIEWS - 1] + [fund_reviews[0]]
    # An empty new account needs one honest input task, never invented analysis.
    if not selected and reviews:
        selected = reviews[:1]
    selected_ids = {row["id"] for row in selected}
    return selected, [row for row in reviews if row["id"] not in selected_ids]


def build_decision_suggestions(*, twin: dict[str, Any], analysis_bits: dict[str, Any],
                             sector_opportunity: dict[str, Any], goal_likelihood: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reviewed = build_grounded_reviews(twin, analysis_bits)
    selected, deferred = focus_reviews(reviewed["items"], objective=str(analysis_bits.get("objective") or ""))
    items = rank_suggestions(selected)
    summary = f"First review: {items[0]['title'].rstrip('.')}." if items else reviewed["summary"]
    if len(items) > 1:
        summary += " Next: " + ", ".join(row["topic_label"].lower() for row in items[1:3]) + "."
    return {
        "available": bool(items), "summary": summary, "items": items,
        "coverage": {**reviewed["coverage"], "primary_limit": MAX_PRIMARY_REVIEWS,
                     "selected_count": len(items), "themes": [row["theme"] for row in items],
                     "deferred_count": len(deferred), "deferred_reviews": deferred,
                     "presentation_policy": "At most four distinct primary reviews; source-coverage tasks and additional findings remain in supporting evidence."},
        "explanation_version": "applied-principles-v1",
        "ranking": {
            "version": "review-priority-v3-focused",
            "method": "At most four distinct primary reviews, retaining a supported fund or bond review for its selected objective. Source-coverage tasks and further findings stay in the supporting record. Explicit application-triage scores order the selected findings; no filler minimum. Relative support = this card's policy score / the sum for this selected list.",
            "interpretation": "Relative review priority, not a probability of profit or goal success. Skills support the reasoning; they do not prescribe these policy scores or prove future outcomes.",
        },
        "ai_used": False,
        "disclaimer": "Review facts, assumptions and applicable records before taking action. Exact skill citations and arithmetic support a conditional review, not a trade instruction or financial-outcome guarantee.",
    }
