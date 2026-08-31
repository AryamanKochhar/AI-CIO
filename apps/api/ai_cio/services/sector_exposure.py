"""User sector exposure from direct equity holdings only."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.services.portfolio import list_holdings
from ai_cio.services.sector_classification import lookup_sector

ZERO = Decimal("0")


def _dec(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def calculate_sector_exposure(db: Session, user_id: int) -> dict[str, Any]:
    holdings = list_holdings(db, user_id)
    equity = [h for h in holdings if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY"]
    mutual_funds = [h for h in holdings if h not in equity]

    buckets: dict[str, dict] = {}
    unknown_value = ZERO
    direct_total = ZERO

    for row in equity:
        val = _dec(row.get("valuation"))
        direct_total += val
        sector = lookup_sector(db, row.get("isin"))
        if not sector:
            unknown_value += val
            key = "unknown"
            label = "Unknown sector"
        else:
            key = sector["sector_index_code"] or sector["sector_name"]
            label = sector["sector_name"]
        bucket = buckets.setdefault(
            key,
            {
                "sector_index_code": sector.get("sector_index_code") if sector else None,
                "sector_name": label,
                "value": ZERO,
                "exposure_type": "direct",
                "holdings": [],
            },
        )
        bucket["value"] += val
        bucket["holdings"].append(
            {
                "scheme_name": row.get("scheme_name"),
                "isin": row.get("isin"),
                "valuation": f"{val:.2f}",
            }
        )

    sectors = []
    for bucket in buckets.values():
        weight = (bucket["value"] / direct_total * Decimal("100")).quantize(Decimal("0.01")) if direct_total > 0 else None
        sectors.append(
            {
                **bucket,
                "value": f"{bucket['value']:.2f}",
                "weight_percent": f"{weight:.2f}" if weight is not None else None,
            }
        )
    sectors.sort(key=lambda s: Decimal(s["value"]), reverse=True)

    mf_value = sum(_dec(h.get("valuation")) for h in mutual_funds)

    return {
        "direct_equity_value": f"{direct_total:.2f}",
        "mutual_fund_value": f"{mf_value:.2f}",
        "unknown_sector_value": f"{unknown_value:.2f}",
        "sectors": sectors,
        "mutual_fund_lookthrough": {
            "available": False,
            "note": "Sector exposure from mutual funds is not yet fully available.",
        },
        "methodology": "Direct equity holdings mapped via NSE sector index constituents when ISIN is classified.",
    }
