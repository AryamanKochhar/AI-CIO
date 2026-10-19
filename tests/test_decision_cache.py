"""Decision result cache — skip recompute when Twin/portfolio fingerprint matches."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Event, Lock
from time import perf_counter

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from ai_cio.services import identity as identity_svc
from ai_cio.services.decision_cache import (
    compute_input_fingerprint,
    get_cached_decision,
    request_key,
    save_cached_decision,
    get_latest_cached_decision,
    run_cached_decision,
)
from ai_cio.services import decision_cache as cache
from ai_cio.db.models import Cashflow, CachedDecision, Document, FixedDeposit, Fund, Goal, Holding, Liability, Transaction, UserJourney
from ai_cio.services.instruments import DomainError
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
    assert r2.headers["cache-control"] == "private, no-store"


def _owner_request(db):
    user = identity_svc.create_user(db, "Synthetic cache owner")
    request = DecisionRequest.from_payload(user_id=user.id, objective="review_equity_portfolio")
    return user.id, request


def test_fingerprint_detects_in_place_financial_edits_and_old_transactions(db):
    user_id, request = _owner_request(db)
    doc = Document(user_id=user_id, kind="demo_portfolio", filename="synthetic.json")
    db.add(doc); db.flush()
    fund = Fund(user_id=user_id, document_id=doc.id, amc="Synthetic", folio="F", scheme_name="Example")
    db.add(fund); db.flush()
    transactions = [Transaction(user_id=user_id, document_id=doc.id, fund_id=fund.id, date="2026-01-01", transaction_type="PURCHASE", description="Synthetic purchase", amount=Decimal("100"), source_page=1) for _ in range(205)]
    holding = Holding(user_id=user_id, document_id=doc.id, fund_id=fund.id, source_page=1, valuation=Decimal("1000"), asset_class="equity")
    liability = Liability(user_id=user_id, name="Synthetic liability", balance=Decimal("1000"), monthly_payment=Decimal("100"))
    deposit = FixedDeposit(user_id=user_id, bank_name="Synthetic bank", principal=Decimal("5000"), tenure_months=12)
    goal = Goal(user_id=user_id, name="Example goal", target_amount=Decimal("10000"), priority="high")
    db.add_all([*transactions, holding, liability, deposit, goal]); db.flush()
    # Same IDs/count/latest date: the previous last-200-ID fingerprint missed it.
    edits = [(transactions[0], "amount", Decimal("101")), (transactions[-1], "description", "Corrected cost record"), (holding, "asset_class", "debt"), (liability, "monthly_payment", Decimal("150")), (deposit, "tenure_months", 24), (goal, "priority", "low")]
    for row, field, value in edits:
        original = cache.compute_input_fingerprint(db, user_id, request)
        before = getattr(row, field); setattr(row, field, value)
        assert cache.compute_input_fingerprint(db, user_id, request) != original, field
        setattr(row, field, before)
        db.flush()


def test_fingerprint_is_one_read_and_navigation_does_not_invalidate(db, record_testsuite_property):
    user_id, request = _owner_request(db)
    before = cache.compute_input_fingerprint(db, user_id, request)
    db.query(UserJourney).filter_by(user_id=user_id).one().current_step = "analysis"
    db.flush()
    statements = []
    def count(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
    event.listen(db.get_bind(), "before_cursor_execute", count)
    try:
        started = perf_counter()
        after = cache.compute_input_fingerprint(db, user_id, request)
        elapsed = (perf_counter() - started) * 1000
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count)
    assert after == before
    assert len(statements) == 1
    record_testsuite_property("fingerprint_sql_round_trips", len(statements))
    record_testsuite_property("local_fingerprint_ms", round(elapsed, 3))


@pytest.mark.parametrize("offset", [-301, 60])
def test_cache_rejects_expired_and_future_timestamps(db, monkeypatch, offset):
    user_id, request = _owner_request(db)
    monkeypatch.setattr(cache.settings, "DECISION_CACHE_TTL_SECONDS", 300, raising=False)
    fp = cache.compute_input_fingerprint(db, user_id, request)
    save_cached_decision(db, user_id=user_id, request=request, fingerprint=fp, result={"decision": "Saved"})
    row = db.query(CachedDecision).filter_by(user_id=user_id).one()
    row.updated_at = cache._now() + timedelta(seconds=offset)
    db.commit()
    assert get_cached_decision(db, user_id=user_id, request=request, fingerprint=fp) is None
    assert get_latest_cached_decision(db, user_id=user_id)["stale"] is True


def test_cache_invalidates_configuration_and_knowledge_changes(db, monkeypatch, tmp_path):
    user_id, request = _owner_request(db)
    monkeypatch.setattr(cache.settings, "ROOT", tmp_path)
    knowledge = tmp_path / "knowledge"; knowledge.mkdir()
    source = knowledge / "finance_sources.json"; source.write_text('{"version":1}')
    first = cache.compute_input_fingerprint(db, user_id, request)
    source.write_text('{"version":2,"reviewed":true}')
    assert cache.compute_input_fingerprint(db, user_id, request) != first
    source.write_text('{"version":1}')
    assert cache.compute_input_fingerprint(db, user_id, request) == first
    monkeypatch.setattr(cache.settings, "OPENAI_MODEL", "different-test-model")
    assert cache.compute_input_fingerprint(db, user_id, request) != first


def test_user_isolation_refresh_timestamp_and_bounded_entries(db):
    user_id, request = _owner_request(db)
    other_id, other_request = _owner_request(db)
    fp = cache.compute_input_fingerprint(db, user_id, request)
    save_cached_decision(db, user_id=user_id, request=request, fingerprint=fp, result={"decision": "Only owner"})
    assert get_cached_decision(db, user_id=other_id, request=other_request, fingerprint=fp) is None
    assert get_cached_decision(db, user_id=user_id, request=other_request, fingerprint=fp) is None
    row = db.query(CachedDecision).filter_by(user_id=user_id).one(); row.updated_at = cache._now() - timedelta(seconds=600); db.commit()
    save_cached_decision(db, user_id=user_id, request=request, fingerprint=fp, result={"decision": "Only owner"})
    assert get_cached_decision(db, user_id=user_id, request=request, fingerprint=fp) is not None
    for i in range(cache.MAX_CACHE_ENTRIES_PER_USER + 3):
        variant = DecisionRequest.from_payload(user_id=user_id, objective="review_equity_portfolio", constraints={"variant": i})
        save_cached_decision(db, user_id=user_id, request=variant, fingerprint=str(i), result={"decision": "Synthetic"})
    assert db.query(CachedDecision).filter_by(user_id=user_id).count() == cache.MAX_CACHE_ENTRIES_PER_USER


def test_concurrent_misses_share_one_run_across_engine_connections(db, pg_engine):
    user_id, request = _owner_request(db); db.commit()
    second_engine = create_engine(pg_engine.url)
    gate = Barrier(2); calls = []; calls_lock = Lock()
    def compute(_db, _request):
        with calls_lock: calls.append(1)
        Event().wait(0.1)  # Deliberately overlap a controlled stub, not an LLM benchmark.
        return {"decision_id": "single-generation", "user_id": user_id, "decision": "Synthetic"}
    def worker(engine):
        gate.wait(timeout=10)
        with Session(engine) as work:
            return run_cached_decision(work, request, compute=compute)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(worker, pg_engine); b = executor.submit(worker, second_engine)
            outputs = [a.result(timeout=20), b.result(timeout=20)]
    finally:
        second_engine.dispose()
    assert len(calls) == 1
    assert sorted(row["cache"]["hit"] for row in outputs) == [False, True]


def test_changed_input_during_generation_is_not_cached(db):
    user_id, request = _owner_request(db); db.commit()
    def changes_input(work, _request):
        work.add(Cashflow(user_id=user_id, kind="income", amount=Decimal("1")))
        return {"user_id": user_id, "decision": "Based on old inputs"}
    with pytest.raises(DomainError, match="changed during analysis"):
        run_cached_decision(db, request, compute=changes_input)
    assert db.query(CachedDecision).filter_by(user_id=user_id).count() == 0
