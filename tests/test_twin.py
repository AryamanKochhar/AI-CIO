"""Digital Financial Twin assembly: completeness, provenance, no fabrication."""
from __future__ import annotations

import pytest

from tests.conftest import GOLDEN

pytestmark = pytest.mark.integration


def test_twin_assembly_with_known_and_unknown(client):
    user = client.post("/users", json={"name": "Twin"}).json()
    uid = user["id"]

    # Before anything is provided, everything should be unknown.
    twin = client.get(f"/users/{uid}/twin").json()
    assert twin["user"]["id"] == uid
    assert twin["completeness"]["psychometric"] is False
    assert twin["completeness"]["income"] is False
    assert twin["completeness"]["portfolio"] is False
    assert twin["ready_for_analysis"] is False
    assert twin["financial_position"]["income"]["known"] is False
    assert twin["financial_position"]["income"]["value"] is None

    # Provide finances, goals, psychometrics.
    client.put(f"/users/{uid}/finances", json={"income": "120000", "expenses": "50000", "liquid": "300000"})
    client.post(f"/users/{uid}/goals", json={"name": "Emergency", "goal_type": "emergency", "target_amount": "600000"})

    session = client.post("/assessments/start", json={"user_id": uid}).json()
    for qid, aid in GOLDEN["answers"].items():
        client.post(
            f"/assessments/{session['id']}/responses",
            json={"question_id": qid, "answer": aid, "confidence": 80, "response_time_ms": 20000},
        )
    client.post(f"/assessments/{session['id']}/complete")

    twin = client.get(f"/users/{uid}/twin").json()
    assert twin["completeness"]["psychometric"] is True
    assert twin["completeness"]["income"] is True
    assert twin["completeness"]["goals"] is True
    assert twin["completeness"]["portfolio"] is False  # no CAS uploaded yet
    assert twin["ready_for_analysis"] is False

    assert twin["behaviour"]["status"] == "known"
    assert twin["behaviour"]["source"] == "psychometric_assessment"
    assert twin["behaviour"]["provenance"]["session_id"] == session["id"]
    assert twin["financial_position"]["income"]["value"] == "120000.00"
    assert twin["financial_position"]["income"]["source"] == "user-provided"
    assert twin["goals"]["items"][0]["name"] == "Emergency"
    assert twin["portfolio"]["total_value"]["known"] is False


def test_twin_with_portfolio_from_cas(client, db):
    pdf_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "cas.pdf"
    if not pdf_path.exists():
        pytest.skip("No local CAS PDF in data/")
    user = client.post("/users", json={"name": "Twin CAS"}).json()
    uid = user["id"]
    with pdf_path.open("rb") as handle:
        upload = client.post(
            f"/users/{uid}/documents/cas",
            files={"file": (pdf_path.name, handle, "application/pdf")},
        )
    assert upload.status_code == 200, upload.text
    twin = client.get(f"/users/{uid}/twin").json()
    assert twin["completeness"]["portfolio"] is True
    assert twin["portfolio"]["total_value"]["known"] is True
    assert twin["portfolio"]["total_value"]["source"] == "cas-derived"
    assert twin["portfolio"]["holdings_count"] >= 1


def test_twin_does_not_fabricate_missing_values(client):
    user = client.post("/users", json={"name": "NoFabrication"}).json()
    uid = user["id"]
    client.put(f"/users/{uid}/finances", json={"income": None, "expenses": "10000", "liquid": None})
    twin = client.get(f"/users/{uid}/twin").json()
    assert twin["financial_position"]["income"]["known"] is False
    assert twin["financial_position"]["income"]["value"] is None
    assert twin["financial_position"]["expenses"]["known"] is True
    assert twin["completeness"]["income"] is False


def test_twin_cross_user_isolation(client):
    alice = client.post("/users", json={"name": "Alice Twin"}).json()
    bob = client.post("/users", json={"name": "Bob Twin"}).json()
    client.put(f"/users/{alice['id']}/finances", json={"income": "100000"})
    client.post(f"/users/{alice['id']}/goals", json={"name": "Alice Goal"})

    alice_twin = client.get(f"/users/{alice['id']}/twin").json()
    bob_twin = client.get(f"/users/{bob['id']}/twin").json()
    assert alice_twin["completeness"]["income"] is True
    assert alice_twin["completeness"]["goals"] is True
    assert bob_twin["completeness"]["income"] is False
    assert bob_twin["completeness"]["goals"] is False
    assert bob_twin["financial_position"]["income"]["value"] is None
