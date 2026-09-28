"""FD Agent — specialist over user FDs + scraped bank rate tables."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from ai_cio import settings
from ai_cio.services import finances as finance_svc
from ai_cio.services.fd.holdings import build_fd_intelligence

logger = logging.getLogger(__name__)


def _liquid_amount(db: Session, user_id: int) -> Decimal | None:
    try:
        data = finance_svc.serialize_finances(db, user_id)
        raw = data.get("liquid")
        if raw is None or raw == "":
            return None
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None


def run_fd_agent(db: Session, user_id: int, *, force_refresh_rates: bool = False) -> dict[str, Any]:
    if not getattr(settings, "FD_INTELLIGENCE_ENABLED", True):
        return {
            "available": False,
            "agent": "fd_agent",
            "status": "disabled",
            "reason": "FD_INTELLIGENCE_ENABLED is false",
            "opportunities": [],
            "comments": [],
        }
    liquid = _liquid_amount(db, user_id)
    payload = build_fd_intelligence(
        db,
        user_id,
        liquid=liquid,
        force_refresh_rates=force_refresh_rates,
    )
    payload["fd_implications_for_recommendations"] = []
    return payload


def fd_impact_for_actions(
    fd_payload: dict[str, Any],
    recommended_actions: list[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    summary = fd_payload.get("summary") or {}
    if not fd_payload.get("available"):
        return [
            {
                "note": "FD analysis unavailable — add FDs or wait for rate scrape.",
                "missing_data": True,
            }
        ]
    out.append(
        {
            "label": "FD / CASH POSITION",
            "fd_count": summary.get("fd_count"),
            "total_principal": summary.get("total_principal"),
            "liquid_cash": summary.get("liquid_cash"),
            "note": (
                "Fixed deposits are low-risk debt-like holdings for planning. "
                "Rates shown from public comparison scrape + your booked rates."
            ),
        }
    )
    for alert in (fd_payload.get("maturity_alerts") or [])[:3]:
        out.append({"label": "Maturity alert", "detail": alert.get("reason")})
    for opp in (fd_payload.get("opportunities") or [])[:3]:
        out.append(
            {
                "label": opp.get("type") or "FD opportunity",
                "detail": opp.get("reason"),
            }
        )
    if recommended_actions:
        cashish = [
            a
            for a in recommended_actions
            if any(k in a.lower() for k in ("cash", "liquid", "debt", "fixed", "buffer", "rebalance"))
        ]
        if cashish:
            out.append(
                {
                    "label": "Liquidity / FD caution",
                    "detail": (
                        "Proposed actions may interact with cash buffers or FD liquidity. "
                        "Review maturity ladders and emergency reserve before locking funds."
                    ),
                    "related_actions": cashish[:3],
                }
            )
    return out
