"""MF evidence revision races, without a database or market-data connection."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import timedelta

import pytest

from ai_cio.services import decision_cache as cache
from ai_cio.services.instruments import DomainError
from ai_cio.services.mutual_funds.cache import PublicDataCache
from ai_cio.services.mutual_funds.provider import cache_fingerprint, import_fingerprint
from domain.decision.contracts import DecisionRequest


class _Connection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, *args):
        self.statements.append(str(statement))

    def commit(self):
        pass

    def in_transaction(self):
        return False


@pytest.fixture
def simulated_cache(monkeypatch, tmp_path):
    """Exercise the real single-flight function with only its DB edges stubbed."""
    connection = _Connection()

    class Engine:
        def connect(self):
            return nullcontext(connection)

    class RequestSession:
        def get_bind(self):
            return engine

    engine = Engine()
    monkeypatch.setenv("MUTUAL_FUND_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cache, "Session", lambda **kwargs: nullcontext(object()))
    state = {"stored": None, "saves": 0}
    old_stamp = (cache._now() - timedelta(seconds=1)).isoformat()

    def fingerprint(_work, user_id, _request, *, include_external=True):
        return "financial-v1:" + (cache_fingerprint(user_id) if include_external else "")

    def get_cached(_work, *, user_id, request, fingerprint):
        stored = state["stored"]
        if stored is None or stored["fingerprint"] != fingerprint:
            return None
        return {**deepcopy(stored["result"]), "cache": {"hit": True, "cached_at": old_stamp}}

    def save(_work, *, user_id, request, fingerprint, result):
        state["stored"] = {"fingerprint": fingerprint, "result": deepcopy(result)}
        state["saves"] += 1

    monkeypatch.setattr(cache, "compute_input_fingerprint", fingerprint)
    monkeypatch.setattr(cache, "get_cached_decision", get_cached)
    monkeypatch.setattr(cache, "save_cached_decision", save)
    return RequestSession(), state, connection


def _request():
    return DecisionRequest.from_payload(user_id=1, objective="review_mutual_fund_portfolio")


def test_import_replacement_during_generation_is_rejected_without_replacing_cache(simulated_cache, tmp_path):
    db, state, connection = simulated_cache
    imports = PublicDataCache(tmp_path / "imports")
    imports.write("user:1:disclosure:122639", {"observed_on": "2026-08-31"})
    request = _request()
    old_result = {"user_id": 1, "decision": "Previous verified result"}
    state["stored"] = {"fingerprint": "financial-v1:" + cache_fingerprint(1), "result": old_result}
    previous = deepcopy(state["stored"])
    calls = []

    def compute(_work, _request):
        calls.append(1)
        consumed = imports.read("user:1:disclosure:122639")["payload"]
        # Models an upload after a specialist consumed the older snapshot.
        imports.write("user:1:disclosure:122639", {"observed_on": "2026-09-30"})
        return {"user_id": 1, "decision": "Consumed " + consumed["observed_on"]}

    with pytest.raises(DomainError, match="Mutual-fund evidence changed during analysis"):
        cache.run_cached_decision(db, request, compute=compute, force_refresh=True)
    assert calls == [1]  # No unbounded retries or repeated paid-model calls.
    assert state["stored"] == previous
    assert state["saves"] == 0
    assert any("pg_advisory_unlock" in sql for sql in connection.statements)


def test_public_provider_warmup_is_saved_with_new_revision_and_reused(simulated_cache, tmp_path):
    db, state, _ = simulated_cache
    request = _request()
    before = cache_fingerprint(1)
    calls = []

    def compute(_work, _request):
        calls.append(1)
        PublicDataCache(tmp_path / "public").write("mfapi:history:122639:v1", {"data": []})
        return {"user_id": 1, "decision": "Based on acquired public evidence"}

    first = cache.run_cached_decision(db, request, compute=compute)
    assert first["cache"]["hit"] is False
    assert cache_fingerprint(1) != before
    assert state["stored"]["fingerprint"] == "financial-v1:" + cache_fingerprint(1)
    assert cache.run_cached_decision(db, request, compute=compute)["cache"]["hit"] is True
    assert calls == [1]


@pytest.mark.parametrize("scope", ["user:1", "public"])
def test_import_racing_with_final_fingerprint_capture_is_not_absorbed(simulated_cache, monkeypatch, tmp_path, scope):
    db, state, _ = simulated_cache
    original = cache.compute_input_fingerprint
    calls = 0

    def fingerprint(*args, **kwargs):
        nonlocal calls
        if kwargs.get("include_external", True):
            calls += 1
            if calls == 2:
                PublicDataCache(tmp_path / "imports").write(f"{scope}:benchmark:NIFTY500_TRI", {"points": []})
        return original(*args, **kwargs)

    monkeypatch.setattr(cache, "compute_input_fingerprint", fingerprint)
    with pytest.raises(DomainError, match="Mutual-fund evidence changed during analysis"):
        cache.run_cached_decision(db, _request(), compute=lambda *_: {"user_id": 1, "decision": "Old evidence"})
    assert state["saves"] == 0


def test_another_users_import_does_not_interrupt_this_users_generation(simulated_cache, tmp_path):
    db, state, _ = simulated_cache
    before = import_fingerprint(1)

    def compute(*_):
        PublicDataCache(tmp_path / "imports").write("user:2:disclosure:122639", {"observed_on": "2026-09-30"})
        return {"user_id": 1, "decision": "Scoped result"}

    result = cache.run_cached_decision(db, _request(), compute=compute)
    assert result["decision"] == "Scoped result"
    assert import_fingerprint(1) == before
    assert import_fingerprint(2) != before
    assert state["saves"] == 1
