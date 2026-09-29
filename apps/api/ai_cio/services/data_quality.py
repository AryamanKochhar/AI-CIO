"""Aggregate data-quality signals already present in Twin / tax / portfolio outputs.

Does not silently overwrite conflicts. Never invents completeness.
"""
from __future__ import annotations

from typing import Any


def build_data_quality_report(
    *,
    twin: dict[str, Any] | None,
    tax_intelligence: dict[str, Any] | None = None,
    concentration_analysis: dict[str, Any] | None = None,
    trajectory_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    twin = twin or {}
    tax = tax_intelligence if isinstance(tax_intelligence, dict) else {}
    traj = trajectory_intelligence if isinstance(trajectory_intelligence, dict) else {}
    completeness = twin.get("completeness") if isinstance(twin.get("completeness"), dict) else {}

    items: list[dict[str, Any]] = []

    for key, label in (
        ("psychometric", "Psychometric profile"),
        ("income", "Income"),
        ("expenses", "Expenses"),
        ("liquid", "Liquid savings"),
        ("goals", "Goals"),
        ("portfolio", "Portfolio holdings"),
        ("horizon", "Goal horizons"),
    ):
        known = completeness.get(key)
        if known is True:
            items.append({"label": label, "status": "verified", "detail": "Present on Twin.", "source": "twin.completeness"})
        elif known is False:
            items.append({"label": label, "status": "incomplete", "detail": "Missing or unknown on Twin.", "source": "twin.completeness"})
        else:
            items.append({"label": label, "status": "unknown", "detail": "Not assessed.", "source": "twin.completeness"})

    tax_dq = tax.get("data_quality") if isinstance(tax.get("data_quality"), dict) else {}
    missing_tax = list(tax.get("missing_data") or [])
    if tax.get("available"):
        usable = tax_dq.get("usable_cost_lots")
        insuff = tax_dq.get("insufficient")
        if insuff and int(insuff) > 0:
            items.append(
                {
                    "label": "Tax cost basis",
                    "status": "incomplete",
                    "detail": f"{insuff} holding(s) lack usable cost lots; {usable or 0} usable.",
                    "source": "tax_intelligence.data_quality",
                }
            )
        elif usable is not None:
            items.append(
                {
                    "label": "Tax cost basis",
                    "status": "verified",
                    "detail": f"{usable} usable cost lot group(s).",
                    "source": "tax_intelligence.data_quality",
                }
            )
        for m in missing_tax[:4]:
            items.append(
                {
                    "label": "Tax data gap",
                    "status": "incomplete",
                    "detail": str(m),
                    "source": "tax_intelligence.missing_data",
                }
            )
    elif tax.get("status") in {"skipped", "disabled"}:
        items.append(
            {
                "label": "Tax intelligence",
                "status": "unknown",
                "detail": "Tax agent not evaluated for this decision.",
                "source": "tax_intelligence",
            }
        )
    elif tax:
        items.append(
            {
                "label": "Tax intelligence",
                "status": "incomplete",
                "detail": tax.get("reason") or "Tax analysis unavailable.",
                "source": "tax_intelligence",
            }
        )

    # Stale portfolio provenance if statement dates exist
    port = twin.get("portfolio") if isinstance(twin.get("portfolio"), dict) else {}
    provenance = twin.get("provenance") if isinstance(twin.get("provenance"), dict) else {}
    period_end = provenance.get("period_end") or port.get("as_of")
    if period_end:
        items.append(
            {
                "label": "Statement freshness",
                "status": "verified",
                "detail": f"Portfolio statement period end / as-of: {period_end}",
                "source": "twin.provenance",
            }
        )
    elif completeness.get("portfolio"):
        items.append(
            {
                "label": "Statement freshness",
                "status": "stale",
                "detail": "Holdings present but statement as-of date not available — treat prices as potentially stale.",
                "source": "twin.portfolio",
            }
        )

    behavior = traj.get("behavior") if isinstance(traj.get("behavior"), dict) else {}
    if behavior.get("available") is False and "transaction_history" in (behavior.get("missing_data") or []):
        items.append(
            {
                "label": "Transaction history",
                "status": "incomplete",
                "detail": "Fewer than 3 dated transactions — observed behaviour limited.",
                "source": "trajectory.behavior",
            }
        )

    conc = concentration_analysis or {}
    if conc.get("unmapped_holdings") or conc.get("unidentified_count"):
        items.append(
            {
                "label": "Security identity",
                "status": "conflicting",
                "detail": "Some holdings could not be fully identified or mapped.",
                "source": "concentration_analysis",
            }
        )

    counts = {"verified": 0, "incomplete": 0, "conflicting": 0, "stale": 0, "unknown": 0}
    for it in items:
        st = it.get("status") or "unknown"
        if st in counts:
            counts[st] += 1
        else:
            counts["unknown"] += 1

    # Confidence hint for CIO
    confidence_note = None
    if counts["conflicting"] > 0:
        confidence_note = "Confidence: Medium — conflicting or unresolved identity signals."
    elif counts["incomplete"] >= 3:
        confidence_note = "Confidence: Medium — multiple incomplete inputs."
    elif counts["incomplete"] > 0 and tax_dq.get("insufficient"):
        confidence_note = "Confidence: Medium — cost basis unavailable for some holdings."
    elif counts["stale"] > 0:
        confidence_note = "Confidence: Medium — statement freshness uncertain."
    elif counts["verified"] >= 4 and counts["incomplete"] == 0:
        confidence_note = "Confidence: High — core Twin inputs present."
    else:
        confidence_note = "Confidence: Medium — partial Twin coverage."

    return {
        "available": True,
        "counts": counts,
        "items": items,
        "confidence_note": confidence_note,
        "disclaimer": (
            "Data quality reflects completeness signals already on Twin/tax/trajectory. "
            "Conflicts are surfaced, not overwritten."
        ),
    }
