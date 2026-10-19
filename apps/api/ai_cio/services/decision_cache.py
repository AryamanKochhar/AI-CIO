"""User-scoped persisted decisions with bounded freshness and single-flight runs.

Cache validation hashes authoritative rows in one PostgreSQL round trip. It does
not rebuild the Twin, fetch market data, or invoke an agent. External data is
bounded by the result TTL; this is a cached analysis, never a live-price claim.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterator
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_cio import settings
from ai_cio.db.models import CachedDecision
from ai_cio.services.instruments import DomainError
from domain.decision.contracts import DecisionRequest

logger = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = "v7-content-fingerprint-ttl"
MAX_CACHE_ENTRIES_PER_USER = 12

# These are source inputs, not outputs, cache tables, login credentials, or
# volatile assembly timestamps. Full financial rows detect in-place edits.
_USER_TABLES = (
    "documents", "funds", "holdings", "transactions", "portfolio_snapshots",
    "goals", "cashflows", "liabilities", "constraints", "fixed_deposits",
    "behavioral_profiles", "assessment_sessions",
)
_PUBLIC_SETTINGS = (
    "EQUITY_AGENT_ENABLED", "EQUITY_LLM_PROVIDER", "OPENAI_MODEL",
    "OPENROUTER_MODEL", "LLM_ENABLED", "LLM_PROVIDER", "LLM_MODEL",
    "OPPORTUNITY_ANALYSIS_PROMPT_VERSION", "SECTOR_OPPORTUNITY_ENABLED",
    "TAX_INTELLIGENCE_ENABLED", "FD_INTELLIGENCE_ENABLED",
    "TRAJECTORY_INTELLIGENCE_ENABLED", "TRENDLYNE_SECTOR_DAY_CHANGE_ENABLED",
    "MARKET_CACHE_TTL_SECONDS", "TRENDLYNE_SECTOR_CACHE_TTL_SECONDS",
    "OPPORTUNITY_SECTOR_CHANGE_THRESHOLD", "OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD",
    "OPPORTUNITY_EXPOSURE_THRESHOLD_PCT", "PARSER_VERSION",
)
_source_lock = Lock()
_source_signature: tuple | None = None
_source_digest: str | None = None
_locks_guard = Lock()
_locks: dict[tuple[int, int, str], tuple[Lock, int]] = {}


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cache_ttl_seconds() -> int:
    # A typo cannot accidentally create an indefinitely fresh financial result.
    try:
        return max(0, min(int(getattr(settings, "DECISION_CACHE_TTL_SECONDS", 300)), 3600))
    except (TypeError, ValueError):
        return 0


def request_key(request: DecisionRequest) -> str:
    return _stable_hash({
        "objective": request.objective.value,
        "available_capital": request.available_capital,
        "constraints": request.constraints or {},
        "requested_action": request.requested_action,
    })


def _source_version() -> str:
    """Memoize content hashes, invalidating on source/knowledge file changes."""
    global _source_signature, _source_digest
    root = Path(settings.ROOT)
    files = set()
    for folder in (root / "apps/api/ai_cio/services", root / "apps/api/domain"):
        if folder.is_dir():
            files.update(folder.rglob("*.py"))
    for folder in (root / "knowledge", root / ".cursor/skills"):
        if folder.is_dir():
            files.update(folder.rglob("*.md"))
            files.update(folder.rglob("*.json"))
    instrument = Path(settings.INSTRUMENT_PATH)
    if instrument.is_file():
        files.add(instrument)
    ordered = sorted(files, key=str)
    signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in ordered)
    with _source_lock:
        if signature != _source_signature or _source_digest is None:
            digest = hashlib.sha256()
            for path in ordered:
                digest.update(str(path.relative_to(root) if path.is_relative_to(root) else path.name).encode())
                digest.update(path.read_bytes())
            _source_signature, _source_digest = signature, digest.hexdigest()
        return _source_digest


def _configuration_version() -> str:
    public = {name: getattr(settings, name, None) for name in _PUBLIC_SETTINGS}
    # Only availability and public endpoint identities, never credential values.
    public["equity_configured"] = settings.equity_llm_configured()
    public["gateway_configured"] = bool(getattr(settings, "LITELLM_API_KEY", ""))
    public["dhan_configured"] = bool(getattr(settings, "DHAN_CLIENT_ID", "") and (
        getattr(settings, "DHAN_ACCESS_TOKEN", "") or (
            getattr(settings, "DHAN_PIN", "") and getattr(settings, "DHAN_TOTP_SECRET", ""))))
    for name in ("OPENAI_BASE_URL", "OPENROUTER_BASE_URL", "LITELLM_BASE_URL"):
        endpoint = urlsplit(getattr(settings, name, "") or "")
        public[name] = (endpoint.scheme, endpoint.hostname, endpoint.port, endpoint.path)
    return _stable_hash(public)


def _row_digest(query: str) -> str:
    return f"(SELECT md5(COALESCE(jsonb_agg(to_jsonb(r) ORDER BY r.id)::text, '[]')) FROM ({query}) AS r)"


def _fingerprint_statement() -> str:
    parts = [f"'{name}', {_row_digest(f'SELECT * FROM {name} WHERE user_id = :user_id')}" for name in _USER_TABLES]
    parts.extend([
        "'user', " + _row_digest("SELECT id, name FROM users WHERE id = :user_id"),
        "'responses', " + _row_digest("SELECT ar.* FROM assessment_responses ar JOIN assessment_sessions s ON s.id = ar.session_id WHERE s.user_id = :user_id"),
        "'instruments', " + _row_digest("SELECT * FROM instruments WHERE id IN (SELECT instrument_id FROM assessment_sessions WHERE user_id = :user_id)"),
        "'securities', " + _row_digest("SELECT * FROM securities WHERE isin IN (SELECT isin FROM funds WHERE user_id = :user_id)"),
        # A read can create the default journey. Navigation, decision notes,
        # record IDs and updated_at do not change financial completeness.
        "'journey', COALESCE((SELECT jsonb_build_object('finances_status', finances_status, 'goals_status', goals_status, 'portfolio_status', portfolio_status) FROM user_journeys WHERE user_id = :user_id), '{\"finances_status\":\"not_started\",\"goals_status\":\"not_started\",\"portfolio_status\":\"not_started\"}'::jsonb)",
    ])
    return "SELECT jsonb_build_object(" + ", ".join(parts) + ")"


_FINGERPRINT_SQL = text(_fingerprint_statement())


def compute_input_fingerprint(db: Session, user_id: int, request: DecisionRequest) -> str:
    if request.user_id != user_id:
        raise DomainError("Decision request user does not match the cache user")
    db.flush()
    rows = db.execute(_FINGERPRINT_SQL, {"user_id": user_id}).scalar_one()
    return _stable_hash({
        "schema": CACHE_SCHEMA_VERSION, "user_id": user_id, "request": request_key(request),
        "financial_rows": rows, "configuration": _configuration_version(),
        "source": _source_version(), "calculation_date": date.today().isoformat(),
    })


def _timestamp(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _fresh(row: CachedDecision) -> bool:
    stamp = _timestamp(row.updated_at)
    now = _now()
    return stamp is not None and timedelta(0) <= now - stamp < timedelta(seconds=cache_ttl_seconds())


def _result(row: CachedDecision) -> dict[str, Any] | None:
    stored = dict(row.result or {})
    if stored.get("user_id") != row.user_id:
        return None
    result = {k: v for k, v in stored.items() if k not in {"_cache_request", "cache"}}
    stamp = _timestamp(row.updated_at)
    result["cache"] = {
        "hit": True, "cached_at": stamp.isoformat() if stamp else None,
        "expires_at": (stamp + timedelta(seconds=cache_ttl_seconds())).isoformat() if stamp else None,
        "ttl_seconds": cache_ttl_seconds(), "input_fingerprint": row.input_fingerprint,
        "note": "Saved analysis reused after checking current financial inputs; market context is from the saved run.",
    }
    return result


def get_cached_decision(db: Session, *, user_id: int, request: DecisionRequest, fingerprint: str | None = None) -> dict[str, Any] | None:
    if request.user_id != user_id:
        return None
    row = db.query(CachedDecision).filter_by(user_id=user_id, objective=request.objective.value, request_key=request_key(request)).one_or_none()
    if row is None or not _fresh(row):
        return None
    current = fingerprint or compute_input_fingerprint(db, user_id, request)
    if row.input_fingerprint != current:
        return None
    return _result(row)


def save_cached_decision(db: Session, *, user_id: int, request: DecisionRequest, fingerprint: str, result: dict[str, Any]) -> None:
    if request.user_id != user_id or result.get("user_id", user_id) != user_id:
        raise DomainError("Decision result user does not match the cache user")
    objective = request.objective.value
    payload = {k: v for k, v in result.items() if k not in {"cache", "_cache_request"}}
    payload["user_id"] = user_id
    payload["_cache_request"] = {"objective": objective, "available_capital": str(request.available_capital) if request.available_capital is not None else None, "constraints": dict(request.constraints or {}), "requested_action": request.requested_action}
    stamp = _now()
    statement = insert(CachedDecision).values(user_id=user_id, objective=objective, request_key=request_key(request), input_fingerprint=fingerprint, result=payload, created_at=stamp, updated_at=stamp)
    db.execute(statement.on_conflict_do_update(index_elements=["user_id", "objective", "request_key"], set_={"input_fingerprint": fingerprint, "result": payload, "updated_at": stamp}))
    keep = [row[0] for row in db.query(CachedDecision.id).filter_by(user_id=user_id).order_by(CachedDecision.updated_at.desc(), CachedDecision.id.desc()).limit(MAX_CACHE_ENTRIES_PER_USER).all()]
    db.query(CachedDecision).filter(CachedDecision.user_id == user_id, ~CachedDecision.id.in_(keep)).delete(synchronize_session=False)
    db.commit()
    db.expire_all()


def _stale(row: CachedDecision, reason: str) -> dict[str, Any]:
    stamp = _timestamp(row.updated_at)
    return {"available": False, "stale": True, "reason": reason, "cache": {"hit": False, "stale": True, "cached_at": stamp.isoformat() if stamp else None}}


def get_latest_cached_decision(db: Session, *, user_id: int, objective: str | None = None) -> dict[str, Any] | None:
    query = db.query(CachedDecision).filter_by(user_id=user_id)
    if objective:
        query = query.filter_by(objective=objective)
    row = query.order_by(CachedDecision.updated_at.desc()).first()
    if row is None:
        return None
    if not _fresh(row):
        return _stale(row, "Saved analysis expired. Run a new analysis for current context.")
    meta = (row.result or {}).get("_cache_request")
    if not isinstance(meta, dict):
        return _stale(row, "Saved analysis has no verifiable request. Run again.")
    try:
        request = DecisionRequest.from_payload(user_id=user_id, objective=meta.get("objective") or row.objective, available_capital=meta.get("available_capital"), constraints=meta.get("constraints") or {}, requested_action=meta.get("requested_action"))
    except (TypeError, ValueError):
        return _stale(row, "Saved analysis request cannot be verified. Run again.")
    if compute_input_fingerprint(db, user_id, request) != row.input_fingerprint:
        return _stale(row, "Your financial inputs or analysis configuration changed. Run again.")
    return _result(row) or _stale(row, "Saved analysis could not be verified for this user.")


@contextmanager
def _local_guard(key: tuple[int, int, str]) -> Iterator[None]:
    with _locks_guard:
        lock, count = _locks.get(key, (Lock(), 0))
        _locks[key] = lock, count + 1
    try:
        with lock:
            yield
    finally:
        with _locks_guard:
            _, count = _locks[key]
            if count == 1:
                del _locks[key]
            else:
                _locks[key] = lock, count - 1


def run_cached_decision(db: Session, request: DecisionRequest, *, compute: Callable[[Session, DecisionRequest], dict[str, Any]], force_refresh: bool = False) -> dict[str, Any]:
    """Serialize identical runs across threads and PostgreSQL-backed workers.

    A Session bound to an explicitly owned connection keeps the session-level
    advisory lock on that connection even when analysis helpers commit. Only one
    pool connection per run is needed. Failed runs never replace a valid cache.
    """
    requested_at = _now()
    engine = db.get_bind()
    key = request_key(request)
    lock_id = int.from_bytes(hashlib.sha256(f"aicio-decision:{request.user_id}:{key}".encode()).digest()[:8], "big", signed=True)
    with _local_guard((id(engine), request.user_id, key)):
        with engine.connect() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '125s'"))
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
            connection.commit()
            try:
                with Session(bind=connection, expire_on_commit=False) as work:
                    fingerprint = compute_input_fingerprint(work, request.user_id, request)
                    hit = get_cached_decision(work, user_id=request.user_id, request=request, fingerprint=fingerprint)
                    if hit is not None:
                        cached_at = datetime.fromisoformat(hit["cache"]["cached_at"])
                        if not force_refresh or cached_at >= requested_at:
                            return hit
                    result = compute(work, request)
                    if compute_input_fingerprint(work, request.user_id, request) != fingerprint:
                        raise DomainError("Financial inputs changed during analysis. Please run again.")
                    save_cached_decision(work, user_id=request.user_id, request=request, fingerprint=fingerprint, result=result)
                    saved = get_cached_decision(work, user_id=request.user_id, request=request, fingerprint=fingerprint)
                    output = dict(result)
                    output["cache"] = {**(saved or {}).get("cache", {}), "hit": False, "forced": force_refresh, "note": "Fresh analysis computed and saved for this user."}
                    return output
            finally:
                try:
                    if connection.in_transaction():
                        connection.rollback()
                    connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
                    connection.commit()
                except Exception:
                    # Never return a connection holding a lock to the pool.
                    connection.invalidate()
                    raise
