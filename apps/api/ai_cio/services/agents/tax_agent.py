"""Tax Agent — specialist that explains deterministic tax engine outputs.

Does not invent tax law or fabricate numbers.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ai_cio import settings
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services.tax.engine import build_tax_intelligence

logger = logging.getLogger(__name__)


def run_tax_agent(db: Session, user_id: int, *, financial_year: str | None = None) -> dict[str, Any]:
    if not getattr(settings, "TAX_INTELLIGENCE_ENABLED", True):
        return {
            "available": False,
            "agent": "tax_agent",
            "status": "disabled",
            "reason": "TAX_INTELLIGENCE_ENABLED is false",
            "opportunities": [],
            "comments": [],
        }
    holdings = portfolio_svc.list_holdings(db, user_id)
    transactions = portfolio_svc.list_transactions(db, user_id)
    payload = build_tax_intelligence(holdings, transactions, financial_year=financial_year)
    payload["tax_implications_for_recommendations"] = []
    return payload


def tax_impact_for_actions(
    tax_payload: dict[str, Any],
    recommended_actions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Attach light-weight tax context to orchestrator recommendations (no inventing)."""
    out: list[dict[str, Any]] = []
    summary = tax_payload.get("summary") or {}
    if not tax_payload.get("available"):
        return [
            {
                "note": "Tax analysis unavailable or incomplete for this recommendation set.",
                "missing_data": tax_payload.get("missing_data") or [],
            }
        ]
    out.append(
        {
            "label": "TAX IMPACT (current year position)",
            "stcg": summary.get("stcg"),
            "ltcg": summary.get("ltcg"),
            "estimated_tax": summary.get("estimated_tax"),
            "note": (
                "Figures reflect realized activity visible in uploaded statements this financial year, "
                "plus unrealized opportunity detection. Not a projection of the proposed trade itself "
                "unless lot-level sale mapping is available."
            ),
        }
    )
    for opp in (tax_payload.get("opportunities") or [])[:3]:
        out.append(
            {
                "label": opp.get("label") or opp.get("type"),
                "detail": opp.get("reason"),
                "estimated_tax_impact": opp.get("estimated_tax_impact"),
                "risks": opp.get("risks") or [],
            }
        )
    if recommended_actions:
        sellish = [a for a in recommended_actions if "sell" in a.lower() or "rebalance" in a.lower()]
        if sellish:
            out.append(
                {
                    "label": "Recommendation tax caution",
                    "detail": (
                        "Proposed actions may realize gains or losses. Review tax lots and holding-period "
                        "alerts before executing. This system does not place trades."
                    ),
                    "related_actions": sellish[:3],
                }
            )
    return out
