"""Unit tests for illustrative goal-hit likelihood math."""
from __future__ import annotations

from decimal import Decimal

from ai_cio.services.goal_likelihood import (
    assess_goal,
    assess_selected_goals,
    parse_goal_ids,
)


def test_parse_goal_ids_list_and_csv():
    assert parse_goal_ids({"goal_ids": [1, "2", 3]}) == [1, 2, 3]
    assert parse_goal_ids({"goal_ids": "4, 5"}) == [4, 5]
    assert parse_goal_ids({}) == []
    assert parse_goal_ids(None) == []


def test_assess_goal_on_track_with_surplus():
    result = assess_goal(
        {
            "id": 1,
            "name": "Home",
            "goal_type": "home",
            "target_amount": "1000000",
            "current_funding": "200000",
            "horizon_years": 10,
        },
        monthly_surplus=Decimal("15000"),
        annual_return=Decimal("0.10"),
    )
    assert result["likelihood_status"] in {"likely", "possible"}
    assert result["projected_corpus"] is not None
    assert result["likelihood_percent"] is not None
    assert "Illustrative" in result["disclaimer"]


def test_assess_goal_missing_inputs():
    result = assess_goal(
        {"id": 2, "name": "Travel", "goal_type": "travel"},
        monthly_surplus=None,
    )
    assert result["likelihood_status"] == "unknown"
    assert "target_amount" in result["missing_inputs"]


def test_assess_selected_goals_filters_ids():
    twin = {
        "financial_position": {
            "income": {"value": "100000"},
            "expenses": {"value": "60000"},
        },
        "goals": {
            "items": [
                {
                    "id": 10,
                    "name": "A",
                    "target_amount": "500000",
                    "current_funding": "0",
                    "horizon_years": 5,
                },
                {
                    "id": 20,
                    "name": "B",
                    "target_amount": "5000000",
                    "current_funding": "0",
                    "horizon_years": 5,
                },
            ]
        },
    }
    rows = assess_selected_goals(twin, [20])
    assert len(rows) == 1
    assert rows[0]["goal_id"] == 20
    assert rows[0]["monthly_surplus_used"] == "40000.00"
