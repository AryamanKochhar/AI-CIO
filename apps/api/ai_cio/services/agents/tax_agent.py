"""Tax Agent — specialist that explains deterministic tax engine outputs.

Does not invent tax law or fabricate numbers.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from ai_cio import settings
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services.tax.engine import build_tax_intelligence

logger = logging.getLogger(__name__)

_INDIAN_SECURITY_ISIN = re.compile(r"INE[A-Z0-9]{9}\Z")
_DIRECT_TYPES = {"equity", "listed_equity"}
_FUND_OR_UNSUPPORTED_TYPES = {"mutual_fund", "mf", "fund", "bond", "debt", "fixed_deposit", "etf",
    "corporate_bond", "government_bond", "gsec", "t_bill", "treasury_bill", "sovereign_gold_bond", "sgb", "sdl", "fixed_income"}


def _direct_equity_marker(row: dict) -> bool:
    """Use recorded type metadata and identity, never a scheme-name guess."""
    asset = str(row.get("asset_class") or "").strip().lower()
    return asset in _DIRECT_TYPES or str(row.get("amc") or "").strip().upper() == "EQUITY"


def _scoped_inputs(holdings: list[dict], transactions: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    def isin(row):
        return str(row.get("isin") or "").strip().upper()

    def eligible(row):
        return bool(_INDIAN_SECURITY_ISIN.fullmatch(isin(row))) and _direct_equity_marker(row) and str(row.get("asset_class") or "").lower() not in _FUND_OR_UNSUPPORTED_TYPES

    supported = {isin(row) for row in holdings if eligible(row)}
    unsupported = {isin(row) for row in [*holdings, *transactions]
                   if str(row.get("asset_class") or "").strip().lower() in _FUND_OR_UNSUPPORTED_TYPES and isin(row)}
    conflicting = ({isin(row) for row in holdings if not eligible(row) and isin(row)} & supported) | unsupported
    supported -= conflicting
    scoped_h, scoped_t, exclusions = [], [], []

    def exclude(row, record_type):
        exclusions.append({"security": row.get("scheme_name") or "Unidentified security", "isin": row.get("isin"),
                           "record_type": record_type, "reason": "unsupported_or_unverified_mf_tax_classification",
                           "detail": "Excluded from numeric special-rate totals. The recorded type and Indian direct-equity identity are not both verified. MF name, plan and debt/equity labels do not establish statutory classification or acquisition-date applicability.",
                           "required": ["Verified asset/tax classification for the applicable income period", "Complete acquisition and disposal lots", "Supported class-specific rule coverage"],
                           "estimated_tax": None})

    for row in holdings:
        if eligible(row) and isin(row) not in conflicting:
            # The legacy lot engine also checks AMC. Normalize only a copy after
            # explicit type/ISIN validation; never infer equity from a name.
            scoped_h.append({**row, "amc": "EQUITY", "asset_class": "equity", "isin": isin(row)})
        else:
            exclude(row, "holding")
    for row in transactions:
        identity = isin(row)
        declared = str(row.get("asset_class") or "").lower()
        matched = identity in supported
        if _INDIAN_SECURITY_ISIN.fullmatch(identity) and identity not in conflicting and declared not in _FUND_OR_UNSUPPORTED_TYPES and (matched or eligible(row)):
            scoped_t.append({**row, "amc": "EQUITY", "isin": identity})
        else:
            exclude(row, "transaction")
    return scoped_h, scoped_t, exclusions


def _apply_scope_guard(payload: dict, *, holdings: list[dict], transactions: list[dict],
                       scoped_h: list[dict], scoped_t: list[dict], exclusions: list[dict]) -> dict:
    if not exclusions:
        payload["calculation_scope"] = {"version": "tax-agent-scope-v1", "numeric_scope": "supported_indian_direct_equity_only",
                                        "excluded_records": 0, "supported_holdings": len(scoped_h), "supported_transactions": len(scoped_t),
                                        "whole_portfolio_tax_estimated": False,
                                        "note": "Configured analytical direct-equity estimate only; personal income, residency, surcharge/cess and external records remain outside this calculation."}
        return payload
    reason = (
        f"Numeric tax estimates cover only the supported Indian direct-equity subset ({len(scoped_h)} holdings, {len(scoped_t)} transactions). "
        f"{len(exclusions)} mutual-fund or unverified records are excluded until classification, dated lots and applicable rule coverage are verified. "
        "Their tax is unknown, not zero. This is not a whole-portfolio tax liability or a prospective MF-switch quote."
    )
    payload["calculation_scope"] = {"version": "tax-agent-scope-v1", "numeric_scope": "supported_indian_direct_equity_only",
                                    "excluded_records": len(exclusions), "original_holdings": len(holdings),
                                    "original_transactions": len(transactions), "supported_holdings": len(scoped_h),
                                    "supported_transactions": len(scoped_t), "whole_portfolio_tax_estimated": False,
                                    "whole_portfolio_exemption_headroom_verified": False, "note": reason}
    payload["reason"] = reason
    payload["missing_data"] = exclusions + list(payload.get("missing_data") or [])
    payload["comments"] = [reason] + ["Supported direct-equity subset only: " + str(c) for c in payload.get("comments") or []]
    payload["assumptions"] = [reason, "Exemption and loss set-off amounts are conditional on this subset. Other eligible gains/losses can change the final annual computation; unused whole-portfolio exemption headroom is not established."] + list(payload.get("assumptions") or [])
    payload["alerts"] = [{"type": "tax_scope_exclusions", "severity": "warning", "title": "Mutual-fund and unverified tax amounts withheld", "detail": reason, "href": "#data-quality"}] + list(payload.get("alerts") or [])
    quality = payload.setdefault("data_quality", {})
    quality.update({"scope_excluded_records": len(exclusions), "scoped_holdings": len(scoped_h),
                    "total_holdings": len(holdings), "message": reason + " " + str(quality.get("message") or "")})
    usable = min(int(quality.get("usable_cost_lots") or 0), len(scoped_h))
    quality["coverage_pct"] = round(100 * usable / len(holdings)) if holdings else 0
    # Whole-portfolio headroom cannot be established while eligible MF gains are
    # excluded. Do not turn the subset's unused exemption into a gain-harvest CTA.
    payload["opportunities"] = [o for o in payload.get("opportunities") or [] if o.get("type") != "gain_harvesting"]
    if scoped_h or scoped_t:
        payload["engine_status_before_scope_guard"] = payload.get("status")
        payload["status"] = "partial"
    else:
        payload.update({"available": False, "status": "not_evaluated", "summary": {},
                        "tax_estimate": {"status": "not_evaluated", "reason": reason},
                        "by_security": [], "opportunities": [], "holding_period_events": [],
                        "tax_lots": {"realized": [], "unrealized": []},
                        "loss_inventory": {"carry_forward_history": "unavailable", "note": reason},
                        "comments": [reason]})
        quality["coverage_pct"] = 0
    return payload


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
    if getattr(db, "decision_snapshot", False):
        holdings, transactions = db.holdings, db.transactions
    else:
        holdings = portfolio_svc.list_holdings(db, user_id)
        transactions = portfolio_svc.list_transactions(db, user_id)
    scoped_h, scoped_t, exclusions = _scoped_inputs(holdings, transactions)
    payload = build_tax_intelligence(scoped_h, scoped_t, financial_year=financial_year)
    payload = _apply_scope_guard(payload, holdings=holdings, transactions=transactions,
                                scoped_h=scoped_h, scoped_t=scoped_t, exclusions=exclusions)
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
            "label": "TAX IMPACT (supported direct-equity subset)" if (tax_payload.get("calculation_scope") or {}).get("excluded_records") else "TAX IMPACT (current year position)",
            "stcg": summary.get("stcg"),
            "ltcg": summary.get("ltcg"),
            "estimated_tax": summary.get("estimated_tax"),
            "note": ((tax_payload.get("calculation_scope") or {}).get("note", "") + " " + (
                "Figures reflect realized activity visible in uploaded statements this financial year, "
                "plus unrealized opportunity detection. Not a projection of the proposed trade itself "
                "unless lot-level sale mapping is available."
            )).strip(),
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
