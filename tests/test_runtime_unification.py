"""Integration tests for FastAPI + Postgres + MCP domain reads."""
from __future__ import annotations

import pytest

from tests.conftest import GOLDEN, ROOT, _synthetic_result

pytestmark = pytest.mark.integration


def test_user_creation(client):
    response = client.post("/users", json={"name": "Ada"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] >= 1
    assert body["name"] == "Ada"


def test_question_retrieval_from_backend(client):
    response = client.get("/instruments/current/questions")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.0"
    assert len(body["questions"]) == 18
    assert "score" not in body["questions"][0]["options"][0]


def _complete_golden(client, name="Casey"):
    user = client.post("/users", json={"name": name}).json()
    session = client.post("/assessments/start", json={"user_id": user["id"]}).json()
    for question_id, answer_id in GOLDEN["answers"].items():
        posted = client.post(
            f"/assessments/{session['id']}/responses",
            json={
                "question_id": question_id,
                "answer": answer_id,
                "confidence": GOLDEN["confidence"],
                "response_time_ms": GOLDEN["response_time_ms"],
            },
        )
        assert posted.status_code == 200, posted.text
    complete = client.post(f"/assessments/{session['id']}/complete")
    assert complete.status_code == 200, complete.text
    return user, session, complete.json()


def test_psychometric_assessment_and_corrected_scoring(client):
    user, session, profile = _complete_golden(client, "Scorer")
    assert profile["user_id"] == user["id"]
    assert profile["session_id"] == session["id"]
    assert profile["risk_score"] == GOLDEN["expected_scores"]["risk_score"]
    assert profile["loss_aversion_score"] == GOLDEN["expected_scores"]["loss_aversion_score"]
    assert profile["polarity"]["loss_aversion"]["higher_means"].startswith("lower")


def test_response_submission_stores_answer_not_client_score(client, db):
    from ai_cio.db.models import AssessmentResponse

    user = client.post("/users", json={"name": "Audit"}).json()
    session = client.post("/assessments/start", json={"user_id": user["id"]}).json()
    posted = client.post(
        f"/assessments/{session['id']}/responses",
        json={"question_id": "Q002", "answer": "5", "confidence": 80, "response_time_ms": 20000},
    )
    assert posted.status_code == 200
    db.expire_all()
    row = (
        db.query(AssessmentResponse)
        .filter(AssessmentResponse.session_id == session["id"], AssessmentResponse.question_id == "Q002")
        .one()
    )
    assert row.answer_id == "5"
    assert row.score_applied == 1.0


def test_behavioural_profile_persistence(client):
    user, session, profile = _complete_golden(client, "Persist")
    fetched = client.get(f"/assessments/{session['id']}/profile")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == profile["id"]
    latest = client.get(f"/users/{user['id']}/profile")
    assert latest.status_code == 200
    assert latest.json()["session_id"] == session["id"]


def test_cas_persist_and_user_scoped_holdings(db):
    from ai_cio.services.identity import create_user
    from ai_cio.services.portfolio import list_holdings, persist_parse_result

    user = create_user(db, "Holder")
    document = persist_parse_result(db, user.id, _synthetic_result("A"), "a.pdf")
    db.commit()
    holdings = list_holdings(db, user.id)
    assert len(holdings) == 1
    assert holdings[0]["user_id"] == user.id
    assert holdings[0]["document_id"] == document.id
    assert holdings[0]["scheme_name"] == "Fund A"


def test_multiple_documents_are_not_wiped(db):
    from ai_cio.services.identity import create_user
    from ai_cio.services.portfolio import document_count, list_holdings, persist_parse_result

    user = create_user(db, "Docs")
    first = persist_parse_result(db, user.id, _synthetic_result("One"), "one.pdf")
    second = persist_parse_result(db, user.id, _synthetic_result("Two"), "two.pdf")
    db.commit()
    assert document_count(db, user.id) == 2
    latest = list_holdings(db, user.id)
    assert latest[0]["scheme_name"] == "Fund Two"
    older = list_holdings(db, user.id, document_id=first.id)
    assert older[0]["scheme_name"] == "Fund One"
    assert second.id != first.id


def test_cross_user_isolation(db):
    from ai_cio.services.identity import create_user
    from ai_cio.services.instruments import DomainError
    from ai_cio.services.portfolio import list_holdings, persist_parse_result

    alice = create_user(db, "Alice")
    bob = create_user(db, "Bob")
    persist_parse_result(db, alice.id, _synthetic_result("AliceFund"), "alice.pdf")
    persist_parse_result(db, bob.id, _synthetic_result("BobFund"), "bob.pdf")
    db.commit()
    alice_holdings = list_holdings(db, alice.id)
    bob_holdings = list_holdings(db, bob.id)
    assert alice_holdings[0]["scheme_name"] == "Fund AliceFund"
    assert bob_holdings[0]["scheme_name"] == "Fund BobFund"
    with pytest.raises(DomainError):
        list_holdings(db, alice.id, document_id=bob_holdings[0]["document_id"])


def test_cas_parsing_and_upload_when_pdf_present(client, db):
    pdfs = sorted((ROOT / "data").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No local CAS PDF in data/")
    from parser import parse_cas

    parsed = parse_cas(pdfs[0])
    assert parsed.holdings, parsed.warnings
    user = client.post("/users", json={"name": "CAS User"}).json()
    with pdfs[0].open("rb") as handle:
        uploaded = client.post(
            f"/users/{user['id']}/documents/cas",
            files={"file": (pdfs[0].name, handle, "application/pdf")},
        )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["user_id"] == user["id"]
    assert body["holdings"] >= 1
    holdings = client.get(f"/users/{user['id']}/holdings")
    assert holdings.status_code == 200
    assert len(holdings.json()) == body["holdings"]


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    if callable(fn):
        return fn(**kwargs)
    return tool(**kwargs)


def test_mcp_portfolio_and_profile_retrieval(db):
    from ai_cio.services.assessments import complete_assessment, start_assessment, submit_response
    from ai_cio.services.identity import create_user
    from ai_cio.services.portfolio import persist_parse_result
    from server import get_behavioral_profile, get_holdings, get_source

    user = create_user(db, "MCP")
    persist_parse_result(db, user.id, _synthetic_result("MCP"), "mcp.pdf")
    session = start_assessment(db, user.id)
    for question_id, answer_id in GOLDEN["answers"].items():
        submit_response(db, session.id, question_id, answer_id, 80, 20000)
    complete_assessment(db, session.id)
    db.commit()

    holdings = _call(get_holdings, user_id=user.id)
    assert holdings[0]["scheme_name"] == "Fund MCP"
    assert "text" not in holdings[0]
    source = _call(get_source, page=1, user_id=user.id)
    assert "holdings" in source
    assert source.get("text") is None
    profile = _call(get_behavioral_profile, user_id=user.id)
    assert profile["user_id"] == user.id
    assert profile["risk_score"] == GOLDEN["expected_scores"]["risk_score"]


def test_invalid_answer_rejected_by_api(client):
    user = client.post("/users", json={"name": "Reject"}).json()
    session = client.post("/assessments/start", json={"user_id": user["id"]}).json()
    bad = client.post(
        f"/assessments/{session['id']}/responses",
        json={"question_id": "Q001", "answer": "Z", "confidence": 50, "response_time_ms": 1000},
    )
    assert bad.status_code == 400
