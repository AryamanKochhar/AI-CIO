"""Versioned review-priority policy; not a financial outcome model."""
from __future__ import annotations

from typing import Any

PRIORITIES = {"risk": 90, "diversification": 80, "goals": 75, "sector": 60, "general": 40}


def rank_suggestions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize policy weights into an interpretable distribution over this list.

    Scores express review order. No return series, outcome labels, or probability
    calibration data are used, so the distribution cannot predict success.
    Unverified AI-only prose receives a 0.75 evidence factor.
    """
    scored = []
    for index, item in enumerate(items):
        base = PRIORITIES.get(str(item.get("kind", "general")), 40)
        factor = 1.0 if item.get("source") == "rules" else 0.75
        scored.append({**item, "priority_score": round(base * factor, 2),
                       "ranking_basis": f"{item.get('kind', 'general')} priority {base} × evidence factor {factor:g}",
                       "_original": index})
    scored.sort(key=lambda item: (-item["priority_score"], item["_original"]))
    total = sum(item["priority_score"] for item in scored)
    # Largest-remainder allocation gives exactly 100.00%, including equal scores.
    units = [int(item["priority_score"] / total * 10000) for item in scored] if total else []
    residual_order = sorted(range(len(scored)), key=lambda i: (-(scored[i]["priority_score"] / total * 10000 - units[i]), i))
    for index in residual_order[:10000 - sum(units)]:
        units[index] += 1
    for index, item in enumerate(scored):
        item.pop("_original")
        item.update(rank=index + 1, relative_support_percent=units[index] / 100,
                    calibrated_probability=False)
    return scored
