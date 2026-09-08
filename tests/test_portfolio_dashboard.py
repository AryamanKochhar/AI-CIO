"""Tests for portfolio health dashboard."""
from decimal import Decimal

from ai_cio.services.agents.portfolio_dashboard import build_portfolio_dashboard


def test_health_score_and_worries():
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
            "portfolio_snapshot": {
                "number_of_holdings": 4,
                "total_invested_value": "100.00",
                "asset_allocation": {"equity_percent": "30", "other_percent": "70", "cash_percent": None},
            },
            "concentration": {
                "largest_holding_percent": "40.00",
                "top_3_holdings_percent": "90.00",
                "top_5_holdings_percent": "100.00",
                "top_10_holdings_percent": "100.00",
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
    dash = build_portfolio_dashboard(twin=twin, preanalysis=twin["preanalysis"], objective="review_portfolio")
    assert dash["portfolio_health"]["score"] is not None
    assert 0 <= dash["portfolio_health"]["score"] <= 100
    assert dash["portfolio_health"]["components"]["valuation"]["available"] is False
    assert dash["portfolio_health"]["components"]["fund_overlap"]["available"] is False
    assert dash["portfolio_health"]["components"]["diversification"]["available"] is True
    assert len(dash["top_worries"]) <= 5
    assert len(dash["top_worries"]) >= 1
    assert dash["concentration_analysis"]["largest_holding_percent"] == "40.00"
    assert dash["true_exposure"]["sector_exposure"]
    assert dash["true_exposure"]["economic_themes"]
    assert dash["quality_valuation"]["available"] is False
