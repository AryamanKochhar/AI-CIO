"""Deterministic Financial Map view-model tests."""
from __future__ import annotations

from decimal import Decimal

from ai_cio.services.financial_map import build_financial_map


def _base(**overrides):
    payload = dict(
        user_name="Aryaman",
        income=Decimal("100000"),
        expenses=Decimal("40000"),
        liquid=Decimal("200000"),
        liabilities=[{"name": "Education loan", "balance": "150000", "liability_type": "education"}],
        liability_total=Decimal("150000"),
        holdings=[
            {
                "scheme_name": "HDFC Bank",
                "amc": "EQUITY",
                "isin": "INE040A01034",
                "valuation": Decimal("145971"),
                "asset_class": "equity",
                "closing_units": Decimal("196"),
                "nav": Decimal("744.75"),
            },
            {
                "scheme_name": "Parag Parikh Flexi Cap",
                "amc": "PPFAS Mutual Fund",
                "isin": "INF879O01027",
                "folio": "13959081",
                "valuation": Decimal("8936.63"),
                "asset_class": "mutual_fund",
                "invested_amount": Decimal("9000"),
                "unrealised_pl": Decimal("-63.37"),
            },
            {
                "scheme_name": "Kotak Midcap",
                "amc": "Kotak Mutual Fund",
                "isin": "INF174K01LT0",
                "valuation": Decimal("133539.71"),
                "asset_class": "mutual_fund",
            },
        ],
        goals=[
            {
                "id": 1,
                "name": "Retirement",
                "goal_type": "retirement",
                "target_amount": Decimal("5000000"),
                "current_funding": Decimal("800000"),
                "target_date": "2045-01-01",
            }
        ],
        behaviour={"status": "known", "observations": ["You prefer security when facing losses."]},
        completeness={
            "psychometric": True,
            "income": True,
            "expenses": True,
            "liquid": True,
            "liabilities": True,
            "goals": True,
            "portfolio": True,
            "horizon": True,
        },
        provenance={
            "source": "CDSL CAS",
            "period_start": "01-05-2026",
            "period_end": "31-05-2026",
            "document_id": 9,
        },
        portfolio_value=Decimal("288447.34"),
    )
    payload.update(overrides)
    return build_financial_map(**payload)


def test_map_builds_hierarchy_from_available_data():
    result = _base()
    ids = {n["id"] for n in result["nodes"]}
    assert "life" in ids
    assert "cash" in ids
    assert "investments" in ids
    assert "equity" in ids
    assert "mutual_funds" in ids
    assert "goals" in ids
    assert "goal-1" in ids
    assert "liabilities" in ids
    assert any(e["from"] == "life" and e["to"] == "investments" for e in result["edges"])


def test_map_omits_unavailable_branches_honestly():
    result = _base(
        holdings=[],
        portfolio_value=None,
        goals=[],
        liabilities=[],
        liability_total=Decimal("0"),
        liquid=None,
        completeness={
            "psychometric": True,
            "income": True,
            "expenses": True,
            "liquid": False,
            "liabilities": False,
            "goals": False,
            "portfolio": False,
            "horizon": False,
        },
    )
    inv = next(n for n in result["nodes"] if n["id"] == "investments")
    goals = next(n for n in result["nodes"] if n["id"] == "goals")
    cash = next(n for n in result["nodes"] if n["id"] == "cash")
    assert inv["available"] is False
    assert goals["available"] is False
    assert cash["available"] is False
    assert any(i["category"] == "data_gap" for i in result["insights"])


def test_concentration_insight_is_deterministic():
    result = _base()
    titles = [i["title"] for i in result["insights"]]
    assert "Concentration worth reviewing" in titles or "Portfolio concentration" in titles


def test_liquidity_requires_expenses():
    with_exp = _base()
    assert any(i["id"] == "liquidity-cover" for i in with_exp["insights"])
    without = _base(expenses=None)
    assert any(i["id"] == "liquidity-unknown" for i in without["insights"])
    assert not any(i["id"] == "liquidity-cover" for i in without["insights"])


def test_goal_funding_insight_uses_recorded_funding_only():
    result = _base()
    assert any(i["id"] == "goal-cover-1" for i in result["insights"])
    # No invented edges from goals to holdings
    assert not any(e["from"].startswith("goal-") and e["to"].startswith("eq-") for e in result["edges"])
    assert not any(e["from"].startswith("goal-") and e["to"].startswith("mf-") for e in result["edges"])


def test_large_portfolio_clusters_beyond_top_n():
    holdings = [
        {
            "scheme_name": f"Fund {i}",
            "amc": "AMC",
            "isin": f"INF{i:09d}",
            "valuation": Decimal(1000 - i),
            "asset_class": "mutual_fund",
        }
        for i in range(20)
    ]
    result = _base(holdings=holdings, portfolio_value=Decimal("20000"))
    assert any(n["type"] == "cluster" for n in result["nodes"])
