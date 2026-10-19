"""Tests for deterministic portfolio pre-analysis."""
from decimal import Decimal

from ai_cio.services import twin_analytics as analytics


def test_empty_portfolio_snapshot(monkeypatch):
    class DummyDB:
        pass

    monkeypatch.setattr(analytics, "get_user", lambda db, uid: None)
    monkeypatch.setattr(analytics, "list_holdings", lambda db, uid: [])
    monkeypatch.setattr(
        analytics,
        "serialize_finances",
        lambda db, uid: {"income": None, "expenses": None, "liquid": None, "liabilities": []},
    )
    monkeypatch.setattr(analytics, "list_goals", lambda db, uid: [])

    result = analytics.build_portfolio_preanalysis(DummyDB(), 1)
    assert result["portfolio_snapshot"]["number_of_holdings"] == 0
    assert result["portfolio_snapshot"]["total_invested_value"] is None
    assert result["holding_metrics"] == []
    assert result["portfolio_flags"]["missing_portfolio"] is True
    assert result["overlap"]["fund_overlap_available"] is False


def test_concentration_and_holding_weights(monkeypatch):
    class DummyDB:
        pass

    holdings = [
        {
            "amc": "EQUITY",
            "scheme_name": "AAA LTD",
            "isin": "INEAAA",
            "valuation": Decimal("50"),
            "asset_class": "equity",
            "invested_amount": None,
            "unrealised_pl": None,
            "unrealised_pl_pct": None,
        },
        {
            "amc": "Fund A",
            "scheme_name": "MF One",
            "isin": "INF001",
            "valuation": Decimal("30"),
            "asset_class": "mutual_fund",
            "invested_amount": Decimal("25"),
            "unrealised_pl": Decimal("5"),
            "unrealised_pl_pct": Decimal("20"),
        },
        {
            "amc": "Fund B",
            "scheme_name": "MF Two",
            "isin": "INF002",
            "valuation": Decimal("20"),
            "asset_class": "mutual_fund",
            "invested_amount": Decimal("20"),
            "unrealised_pl": Decimal("0"),
            "unrealised_pl_pct": Decimal("0"),
        },
    ]

    monkeypatch.setattr(analytics, "get_user", lambda db, uid: None)
    monkeypatch.setattr(analytics, "list_holdings", lambda db, uid: holdings)
    monkeypatch.setattr(
        analytics,
        "serialize_finances",
        lambda db, uid: {
            "income": "100000",
            "expenses": "40000",
            "cadence": "monthly",
            "liquid": "120000",
            "liabilities": [],
        },
    )
    monkeypatch.setattr(analytics, "list_goals", lambda db, uid: [])
    monkeypatch.setattr(analytics, "lookup_sector", lambda db, isin: None)

    result = analytics.build_portfolio_preanalysis(DummyDB(), 7)
    snap = result["portfolio_snapshot"]
    assert snap["number_of_holdings"] == 3
    assert snap["total_invested_value"] == "100.00"
    # total assets = liquid 120000 + invested 100
    assert snap["total_value"] == "120100.00"
    assert result["concentration"]["largest_holding_percent"] == "50.00"
    assert result["concentration"]["top_3_holdings_percent"] == "100.00"
    assert len(result["holding_metrics"]) == 3
    assert result["holding_metrics"][0]["portfolio_weight_percent"] == "50.00"
    assert result["holding_metrics"][0]["instrument_type"] == "direct_equity"
    assert result["financial_health"]["monthly_surplus"] == "60000.00"
    assert result["financial_health"]["savings_rate_percent"] == "60.00"
    assert result["financial_health"]["liquid_assets_to_monthly_expenses"] == "3.00"
    assert result["portfolio_flags"]["high_single_holding_concentration"] is True
    assert result["portfolio_flags"]["high_single_stock_concentration"] is True
    assert result["portfolio_snapshot"]["instrument_allocation"]["direct_equity_percent"] == "50.00"
    assert result["portfolio_snapshot"]["instrument_allocation"]["mutual_funds_percent"] == "50.00"


def test_goal_remaining(monkeypatch):
    class DummyGoal:
        def __init__(self):
            self.id = 1
            self.user_id = 1
            self.name = "Home"
            self.goal_type = "home"
            self.target_amount = Decimal("1000000")
            self.target_date = "2030-01-01"
            self.current_funding = Decimal("200000")
            self.priority = "high"
            self.flexibility = "somewhat"
            self.horizon_years = 5
            self.notes = None

    class DummyDB:
        pass

    monkeypatch.setattr(analytics, "get_user", lambda db, uid: None)
    monkeypatch.setattr(analytics, "list_holdings", lambda db, uid: [])
    monkeypatch.setattr(
        analytics,
        "serialize_finances",
        lambda db, uid: {"income": None, "expenses": None, "liquid": None, "liabilities": []},
    )
    monkeypatch.setattr(analytics, "list_goals", lambda db, uid: [DummyGoal()])

    result = analytics.build_portfolio_preanalysis(DummyDB(), 1)
    goal = result["goals"][0]
    assert goal["goal_name"] == "Home"
    assert goal["remaining_amount"] == "800000.00"
    assert goal["funding_gap"] == "800000.00"
    assert result["portfolio_flags"]["goal_funding_gap"] is True
