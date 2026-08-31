"""Sanitized Twin context for external LLM — never dump raw Twin JSON."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_sanitized_analysis_context(
    *,
    twin: dict[str, Any],
    sector_name: str | None,
    sector_exposure: dict[str, Any] | None,
    market_facts: list[str],
) -> dict[str, Any]:
    portfolio = twin.get("portfolio") or {}
    behaviour = twin.get("behaviour") or {}
    finances = twin.get("financial_position") or {}
    goals = (twin.get("goals") or {}).get("items") or []
    completeness = twin.get("completeness") or {}

    relevant_holdings: list[dict[str, str]] = []
    if sector_exposure and sector_name:
        for sector in sector_exposure.get("sectors") or []:
            if sector.get("sector_name") == sector_name or sector.get("sector_index_code"):
                for h in sector.get("holdings") or []:
                    relevant_holdings.append(
                        {
                            "name": h.get("scheme_name") or "Holding",
                            "valuation": h.get("valuation"),
                            "isin": h.get("isin"),
                        }
                    )

    liquid = finances.get("liquid") or {}
    liabilities = finances.get("liabilities") or {}

    missing: list[str] = []
    if not completeness.get("portfolio"):
        missing.append("portfolio")
    if not completeness.get("goals"):
        missing.append("goals")
    if sector_exposure and not sector_exposure.get("mutual_fund_lookthrough", {}).get("available"):
        missing.append("mutual_fund_sector_lookthrough")

    return {
        "twin_as_of": datetime.now(timezone.utc).isoformat(),
        "market_facts": market_facts,
        "portfolio": {
            "total_value": (portfolio.get("total_value") or {}).get("value"),
            "holdings_count": portfolio.get("holdings_count"),
            "equity_count": portfolio.get("equity_count"),
            "sector_exposure_value": _sector_value(sector_exposure, sector_name),
            "sector_weight_percent": _sector_weight(sector_exposure, sector_name),
            "relevant_holdings": relevant_holdings[:10],
            "source": (portfolio.get("total_value") or {}).get("source"),
        },
        "goals": [
            {
                "name": g.get("name"),
                "goal_type": g.get("goal_type"),
                "target_amount": g.get("target_amount"),
                "target_date": g.get("target_date"),
                "horizon_years": g.get("horizon_years"),
            }
            for g in goals[:8]
        ],
        "behavioural": {
            "status": behaviour.get("status"),
            "observations": (behaviour.get("observations") or [])[:5],
        },
        "liquidity": {
            "liquid_known": liquid.get("known"),
            "liquid_value": liquid.get("value") if liquid.get("known") else None,
        },
        "liabilities": {
            "known": liabilities.get("known"),
            "total_balance": liabilities.get("total_balance") if liabilities.get("known") else None,
        },
        "completeness": {k: bool(v) for k, v in completeness.items()},
        "missing_information": missing,
    }


def _sector_value(exposure: dict[str, Any] | None, sector_name: str | None) -> str | None:
    if not exposure or not sector_name:
        return None
    for s in exposure.get("sectors") or []:
        if s.get("sector_name") == sector_name:
            return s.get("value")
    return None


def _sector_weight(exposure: dict[str, Any] | None, sector_name: str | None) -> str | None:
    if not exposure or not sector_name:
        return None
    for s in exposure.get("sectors") or []:
        if s.get("sector_name") == sector_name:
            return s.get("weight_percent")
    return None
