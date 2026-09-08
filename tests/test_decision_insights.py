"""Tests for detailed decision insights."""
from decimal import Decimal

from ai_cio.services.agents.decision_insights import build_detailed_insights, build_style_allocation


def test_style_and_sector_insights_for_concentrated_book():
    twin = {
        "portfolio": {
            "holdings_count": 4,
            "holdings": [
                {
                    "scheme_name": "SBI Small Cap Fund",
                    "amc": "SBI",
                    "asset_class": "mutual_fund",
                    "valuation": Decimal("40"),
                },
                {
                    "scheme_name": "Kotak Midcap Fund",
                    "amc": "Kotak",
                    "asset_class": "mutual_fund",
                    "valuation": Decimal("30"),
                },
                {
                    "scheme_name": "HDFC BANK LIMITED",
                    "amc": "EQUITY",
                    "asset_class": "equity",
                    "valuation": Decimal("20"),
                },
                {
                    "scheme_name": "NESTLE INDIA LIMITED",
                    "amc": "EQUITY",
                    "asset_class": "equity",
                    "valuation": Decimal("10"),
                },
            ],
        },
        "goals": {"items": []},
        "behaviour": {"status": "unknown"},
        "preanalysis": {
            "portfolio_snapshot": {"number_of_holdings": 4, "total_invested_value": "100.00"},
            "concentration": {
                "largest_holding_percent": "40.00",
                "top_3_holdings_percent": "90.00",
                "largest_amc_percent": "40.00",
            },
            "portfolio_flags": {
                "high_single_holding_concentration": True,
                "missing_goals": True,
                "missing_finances": True,
            },
            "financial_health": {},
            "sector_allocation": [],
        },
    }
    styles = build_style_allocation(twin["portfolio"]["holdings"])
    assert any(s["style"] == "small_cap" for s in styles)

    insights = build_detailed_insights(twin=twin, preanalysis=twin["preanalysis"], objective="review_portfolio")
    assert insights["recommended_actions"]
    assert any("largest holding" in a.lower() or "25" in a or "40" in a for a in insights["recommended_actions"] + insights["observations"])
    assert insights["insight_cards"]
    assert any(c["type"] in {"concentration", "style_tilt", "sector_tilt"} for c in insights["insight_cards"])
    # Bank equity should create a sector hint action or observation
    assert insights["sector_allocation"]
