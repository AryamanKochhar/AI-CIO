"""Decision result cache — skip recompute when Twin/portfolio fingerprint matches."""
from __future__ import annotations

from ai_cio.services import identity as identity_svc
from ai_cio.services.decision_cache import (
    compute_input_fingerprint,
    get_cached_decision,
    request_key,
    save_cached_decision,
)
from domain.decision.contracts import DecisionRequest


def test_cache_hit_when_fingerprint_unchanged(db):
    user = identity_svc.create_user(db, "Aryaman Kochhar")
    request = DecisionRequest.from_payload(
        user_id=user.id,
        objective="review_equity_portfolio",
        constraints={"goal_ids": [1]},
    )
    fp = compute_input_fingerprint(db, user.id, request)
    save_cached_decision(
        db,
        user_id=user.id,
        request=request,
        fingerprint=fp,
        result={
            "decision_id": "d1",
            "user_id": user.id,
            "objective": "review_equity_portfolio",
            "decision": "Cached finding",
            "rationale": [],
            "key_factors": [],
            "risks": [],
            "tradeoffs": [],
            "assumptions": [],
            "evidence": [],
            "strategy_evaluations": [],
            "validation": {"passed": True, "errors": [], "warnings": []},
            "confidence": "medium",
            "context_summary": {},
            "selected_strategy": None,
            "alternatives": [],
        },
    )
    hit = get_cached_decision(db, user_id=user.id, request=request, fingerprint=fp)
    assert hit is not None
    assert hit["cache"]["hit"] is True
    assert hit["decision"] == "Cached finding"
    assert "_cache_request" not in hit


def test_cache_miss_when_fingerprint_differs(db):
    user = identity_svc.create_user(db, "Aryaman Kochhar")
    request = DecisionRequest.from_payload(
        user_id=user.id,
        objective="review_equity_portfolio",
    )
    save_cached_decision(
        db,
        user_id=user.id,
        request=request,
        fingerprint="old-fingerprint",
        result={"decision": "stale", "objective": "review_equity_portfolio"},
    )
    miss = get_cached_decision(
        db,
        user_id=user.id,
        request=request,
        fingerprint="new-fingerprint",
    )
    assert miss is None


def test_request_key_stable():
    a = DecisionRequest.from_payload(user_id=1, objective="review_equity_portfolio", constraints={"b": 1, "a": 2})
    b = DecisionRequest.from_payload(user_id=1, objective="review_equity_portfolio", constraints={"a": 2, "b": 1})
    assert request_key(a) == request_key(b)


def test_api_returns_cache_on_second_post(client, db):
    user = identity_svc.create_user(db, "Aryaman Kochhar")
    db.commit()
    body = {"objective": "review_equity_portfolio", "constraints": {}}
    # First call may fail validation without portfolio — so seed via save_cached_decision
    # and hit the GET cached + POST with matching fingerprint path.
    request = DecisionRequest.from_payload(user_id=user.id, objective="review_equity_portfolio")
    fp = compute_input_fingerprint(db, user.id, request)
    save_cached_decision(
        db,
        user_id=user.id,
        request=request,
        fingerprint=fp,
        result={
            "decision_id": "cached-api",
            "user_id": user.id,
            "objective": "review_equity_portfolio",
            "decision": "From cache API",
            "rationale": [],
            "key_factors": [],
            "risks": [],
            "tradeoffs": [],
            "assumptions": [],
            "evidence": [],
            "strategy_evaluations": [],
            "validation": {"passed": True, "errors": [], "warnings": []},
            "confidence": "medium",
            "context_summary": {},
            "selected_strategy": None,
            "alternatives": [],
        },
    )
    r = client.get(f"/users/{user.id}/decisions/cached?objective=review_equity_portfolio")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["result"]["decision"] == "From cache API"
    assert data["result"]["cache"]["hit"] is True

    r2 = client.post(f"/users/{user.id}/decisions", json=body)
    assert r2.status_code == 200
    assert r2.json()["cache"]["hit"] is True
    assert r2.json()["decision"] == "From cache API"
