"""Persist and serve DecisionResult when Twin/portfolio inputs are unchanged.

Avoids re-calling equity LLM, Dhan sector APIs, tax rebuild, etc. on every Run.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.db.models import CachedDecision
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services.twin import assemble_twin
from domain.decision.contracts import DecisionRequest

logger = logging.getLogger(__name__)

# Bump when DecisionResult shape gains fields that old cache rows lack.
CACHE_SCHEMA_VERSION = "v4-counterfactual-ai"


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def request_key(request: DecisionRequest) -> str:
    """Hash of user-controlled request params (not full Twin state)."""
    return _stable_hash(
        {
            "objective": request.objective.value if hasattr(request.objective, "value") else str(request.objective),
            "available_capital": request.available_capital,
            "constraints": request.constraints or {},
            "requested_action": request.requested_action,
        }
    )


def compute_input_fingerprint(db: Session, user_id: int, request: DecisionRequest) -> str:
    """Fingerprint of financial inputs that should invalidate a cached decision."""
    twin = assemble_twin(db, user_id)
    holdings = portfolio_svc.list_holdings(db, user_id)
    transactions = portfolio_svc.list_transactions(db, user_id)
    snapshots = portfolio_svc.list_portfolio_snapshots(db, user_id)

    holding_rows = sorted(
        [
            {
                "isin": h.get("isin"),
                "symbol": h.get("symbol") or h.get("scheme_name") or h.get("name"),
                "units": str(h.get("closing_units") or h.get("units") or ""),
                "valuation": str(h.get("valuation") or ""),
                "nav": str(h.get("nav") or ""),
            }
            for h in holdings
        ],
        key=lambda r: (r["isin"] or "", r["symbol"] or ""),
    )
    txn_meta = {
        "count": len(transactions),
        "last_date": max((str(t.get("date") or "") for t in transactions), default=""),
        "ids_hash": _stable_hash(sorted(str(t.get("id") or "") for t in transactions[-200:])),
    }
    goal_rows = []
    for g in (twin.get("goals") or {}).get("items") or []:
        goal_rows.append(
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "target_amount": g.get("target_amount"),
                "current_funding": g.get("current_funding"),
                "target_date": g.get("target_date"),
                "horizon_years": g.get("horizon_years"),
            }
        )
    behaviour = twin.get("behaviour") or {}
    fp = twin.get("financial_position") or {}
    fds = ((fp.get("fixed_deposits") or {}) if isinstance(fp, dict) else {}).get("items") or []

    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "request": {
            "objective": request.objective.value if hasattr(request.objective, "value") else str(request.objective),
            "available_capital": request.available_capital,
            "constraints": request.constraints or {},
            "requested_action": request.requested_action,
        },
        "completeness": twin.get("completeness"),
        "behaviour_scores": behaviour.get("scores") if behaviour.get("status") == "known" else None,
        "behaviour_status": behaviour.get("status"),
        "financial_position": {
            "income": (fp.get("income") or {}).get("value") if isinstance(fp, dict) else None,
            "expenses": (fp.get("expenses") or {}).get("value") if isinstance(fp, dict) else None,
            "liquid": (fp.get("liquid") or {}).get("value") if isinstance(fp, dict) else None,
        },
        "fixed_deposits": sorted(
            [
                {
                    "bank": d.get("bank_name"),
                    "principal": str(d.get("principal") or ""),
                    "maturity": d.get("maturity_date"),
                    "rate": str(d.get("interest_rate_pa") or ""),
                }
                for d in fds
                if isinstance(d, dict)
            ],
            key=lambda r: (r["bank"] or "", r["principal"]),
        ),
        "goals": sorted(goal_rows, key=lambda r: r.get("id") or 0),
        "holdings": holding_rows,
        "transactions": txn_meta,
        "snapshots": [
            {"month_year": s.get("month_year"), "valuation": str(s.get("valuation") or "")}
            for s in snapshots
        ],
    }
    return _stable_hash(payload)


def get_cached_decision(
    db: Session,
    *,
    user_id: int,
    request: DecisionRequest,
    fingerprint: str | None = None,
) -> dict[str, Any] | None:
    req_key = request_key(request)
    fp = fingerprint or compute_input_fingerprint(db, user_id, request)
    row = (
        db.query(CachedDecision)
        .filter(
            CachedDecision.user_id == user_id,
            CachedDecision.objective == (
                request.objective.value if hasattr(request.objective, "value") else str(request.objective)
            ),
            CachedDecision.request_key == req_key,
            CachedDecision.input_fingerprint == fp,
        )
        .one_or_none()
    )
    if not row:
        return None
    result = {k: v for k, v in dict(row.result or {}).items() if k != "_cache_request"}
    result["cache"] = {
        "hit": True,
        "cached_at": row.updated_at.isoformat() if row.updated_at else None,
        "input_fingerprint": row.input_fingerprint,
        "note": "Returned cached decision — Twin/portfolio inputs unchanged. No new LLM or market calls.",
    }
    return result


def save_cached_decision(
    db: Session,
    *,
    user_id: int,
    request: DecisionRequest,
    fingerprint: str,
    result: dict[str, Any],
) -> None:
    objective = request.objective.value if hasattr(request.objective, "value") else str(request.objective)
    req_key = request_key(request)
    # Strip ephemeral cache marker before save
    payload = {k: v for k, v in result.items() if k != "cache"}
    payload["_cache_request"] = {
        "objective": objective,
        "available_capital": str(request.available_capital) if request.available_capital is not None else None,
        "constraints": dict(request.constraints or {}),
        "requested_action": request.requested_action,
    }
    row = (
        db.query(CachedDecision)
        .filter(
            CachedDecision.user_id == user_id,
            CachedDecision.objective == objective,
            CachedDecision.request_key == req_key,
        )
        .one_or_none()
    )
    if row:
        row.input_fingerprint = fingerprint
        row.result = payload
    else:
        row = CachedDecision(
            user_id=user_id,
            objective=objective,
            request_key=req_key,
            input_fingerprint=fingerprint,
            result=payload,
        )
        db.add(row)
    db.commit()
    logger.info(
        "decision_cache_saved user_id=%s objective=%s fingerprint=%s",
        user_id,
        objective,
        fingerprint[:12],
    )


def get_latest_cached_decision(
    db: Session,
    *,
    user_id: int,
    objective: str | None = None,
) -> dict[str, Any] | None:
    q = db.query(CachedDecision).filter(CachedDecision.user_id == user_id)
    if objective:
        q = q.filter(CachedDecision.objective == objective)
    row = q.order_by(CachedDecision.updated_at.desc()).first()
    if not row:
        return None

    stored = dict(row.result or {})
    req_meta = stored.get("_cache_request") if isinstance(stored.get("_cache_request"), dict) else {}
    request = DecisionRequest.from_payload(
        user_id=user_id,
        objective=req_meta.get("objective") or row.objective,
        available_capital=req_meta.get("available_capital"),
        constraints=req_meta.get("constraints") or {},
        requested_action=req_meta.get("requested_action"),
    )
    current_fp = compute_input_fingerprint(db, user_id, request)
    if current_fp != row.input_fingerprint:
        return {
            "available": False,
            "stale": True,
            "reason": "Cached decision exists but Twin/portfolio data changed — re-run required.",
            "cache": {
                "hit": False,
                "stale": True,
                "cached_at": row.updated_at.isoformat() if row.updated_at else None,
                "input_fingerprint": row.input_fingerprint,
                "current_fingerprint": current_fp,
            },
        }
    result = {k: v for k, v in stored.items() if k != "_cache_request"}
    result["cache"] = {
        "hit": True,
        "cached_at": row.updated_at.isoformat() if row.updated_at else None,
        "input_fingerprint": row.input_fingerprint,
        "note": "Loaded cached decision — inputs unchanged.",
    }
    return result
