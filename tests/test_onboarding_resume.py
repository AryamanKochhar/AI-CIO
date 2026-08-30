"""Active assessment resume endpoint."""
from __future__ import annotations

import pytest

from tests.conftest import GOLDEN

pytestmark = pytest.mark.integration


def test_active_assessment_returns_progress(client):
    user = client.post("/users", json={"name": "Resume"}).json()
    session = client.post("/assessments/start", json={"user_id": user["id"]}).json()
    client.post(
        f"/assessments/{session['id']}/responses",
        json={"question_id": "Q001", "answer": GOLDEN["answers"]["Q001"], "confidence": 80, "response_time_ms": 5000},
    )
    active = client.get(f"/users/{user['id']}/assessments/active").json()
    assert active["active"] is True
    assert active["session_id"] == session["id"]
    assert active["answered_count"] == 1
    assert active["total_questions"] == 18


def test_active_assessment_none_when_complete(client):
    user = client.post("/users", json={"name": "Done"}).json()
    session = client.post("/assessments/start", json={"user_id": user["id"]}).json()
    for qid, aid in GOLDEN["answers"].items():
        client.post(
            f"/assessments/{session['id']}/responses",
            json={"question_id": qid, "answer": aid, "confidence": 80, "response_time_ms": 5000},
        )
    client.post(f"/assessments/{session['id']}/complete")
    active = client.get(f"/users/{user['id']}/assessments/active").json()
    assert active["active"] is False


def test_portfolio_confirm_advances_journey(client):
    user = client.post("/users", json={"name": "Confirm"}).json()
    journey = client.post(f"/users/{user['id']}/portfolio/confirm").json()
    assert journey["portfolio_status"] == "provided"
    assert journey["current_step"] == "review"
