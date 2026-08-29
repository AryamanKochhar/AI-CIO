"""Unified journey API: one user_id from psychometrics through review."""
from __future__ import annotations

import pytest

from tests.conftest import GOLDEN

pytestmark = pytest.mark.integration


def test_one_user_finances_goals_review_and_decision(client):
    user = client.post("/users", json={"name": "Journey"}).json()
    uid = user["id"]
    journey = client.get(f"/users/{uid}/journey")
    assert journey.status_code == 200
    assert journey.json()["user_id"] == uid

    finances = client.put(
        f"/users/{uid}/finances",
        json={"income": "100000", "expenses": "40000", "liquid": "250000", "liabilities": []},
    )
    assert finances.status_code == 200, finances.text
    assert finances.json()["income"] == "100000.00"

    skipped = client.put(f"/users/{uid}/finances", json={"skipped": True})
    assert skipped.status_code == 200
    status = client.get(f"/users/{uid}/journey").json()
    assert status["finances_status"] == "skipped"

    goal = client.post(
        f"/users/{uid}/goals",
        json={"name": "Emergency fund", "goal_type": "emergency", "target_amount": "600000", "priority": "high"},
    )
    assert goal.status_code == 200, goal.text
    assert goal.json()["user_id"] == uid
    listed = client.get(f"/users/{uid}/goals").json()
    assert len(listed) == 1

    review = client.get(f"/users/{uid}/review")
    assert review.status_code == 200
    body = review.json()
    assert body["user"]["id"] == uid
    assert body["goals"]["status"] == "known"
    assert body["behaviour"]["status"] == "unknown"
    assert body["finances"]["income"]["status"] == "known"
    assert body["finances"]["income"]["source"] == "user-provided"
    assert body["portfolio"]["total_value"]["status"] == "unknown"
    assert body["portfolio"]["total_value"]["value"] is None

    decision = client.post(
        f"/users/{uid}/review-decision",
        json={"decision": "accept", "notes": "Profile reviewed"},
    )
    assert decision.status_code == 200
    assert decision.json()["decision"] == "accept"
    assert decision.json()["user_id"] == uid


def test_blank_income_stays_unknown(client):
    user = client.post("/users", json={"name": "Unknowns"}).json()
    client.put(f"/users/{user['id']}/finances", json={"income": None, "expenses": "10", "liquid": None})
    review = client.get(f"/users/{user['id']}/review").json()
    assert review["finances"]["income"]["status"] == "unknown"
    assert review["finances"]["income"]["value"] is None
    assert review["finances"]["expenses"]["status"] == "known"
    assert review["completeness"]["income"] is False


def test_goal_and_psychometric_share_user(client):
    user = client.post("/users", json={"name": "Shared"}).json()
    uid = user["id"]
    session = client.post("/assessments/start", json={"user_id": uid}).json()
    for question_id, answer_id in GOLDEN["answers"].items():
        assert (
            client.post(
                f"/assessments/{session['id']}/responses",
                json={
                    "question_id": question_id,
                    "answer": answer_id,
                    "confidence": 80,
                    "response_time_ms": 20000,
                },
            ).status_code
            == 200
        )
    profile = client.post(f"/assessments/{session['id']}/complete").json()
    client.post(f"/users/{uid}/goals", json={"name": "Home", "goal_type": "home"})
    review = client.get(f"/users/{uid}/review").json()
    assert profile["user_id"] == uid
    assert review["behaviour"]["status"] == "known"
    assert review["goals"]["items"][0]["name"] == "Home"
    assert review["user"]["id"] == uid
