"""Market intelligence orchestration — Twin projection + opportunities."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.db.models import MarketOpportunity, MarketOpportunityAnalysis, User, UserAlert
from ai_cio.services import twin as twin_svc
from ai_cio.services.knowledge_retriever import retrieve_knowledge
from ai_cio.services.llm_provider import analyze_opportunity, llm_health
from ai_cio.services.twin_context_builder import build_sanitized_analysis_context
from ai_cio.services.market_data import freshness_label, get_market_snapshots
from ai_cio.services.notifications import build_market_observation_email, deliver_alert_email, resolve_notification_recipient
from ai_cio.services.opportunity_detection import detect_opportunities
from ai_cio.services.sector_exposure import calculate_sector_exposure
from domain.market.analytics import compute_analytics
from domain.market.contracts import TwinAnalysisContext

logger = logging.getLogger(__name__)


def build_public_market_snapshot(db: Session, *, force_fetch: bool = False) -> dict[str, Any]:
    """Market data without user-specific exposure."""
    ctx = build_market_context(db, user_id=-1, force_fetch=force_fetch)
    ctx.pop("sector_exposure", None)
    ctx.pop("observations", None)
    return ctx


def build_market_context(db: Session, user_id: int, *, force_fetch: bool = False) -> dict[str, Any]:
    """Assemble market snapshot, analytics, and user sector exposure for Twin/UI."""
    try:
        snaps = get_market_snapshots(db, force=force_fetch)
    except Exception as exc:
        logger.warning("market_context_fetch_failed user_id=%s err=%s", user_id, exc)
        return {
            "available": False,
            "note": "Market data is temporarily unavailable.",
            "freshness": "unavailable",
            "source": "nse",
        }

    broad = [s for s in snaps if s.category == "broad"]
    sectors = [s for s in snaps if s.category == "sector"]
    benchmark = next((s for s in broad if s.index_code == "NIFTY 50"), broad[0] if broad else None)
    analytics = compute_analytics(sectors=sectors, benchmark=benchmark, is_stale=any(s.is_stale for s in snaps))

    exposure = calculate_sector_exposure(db, user_id) if user_id > 0 else {
        "direct_equity_value": None,
        "sectors": [],
        "mutual_fund_lookthrough": {"available": False, "note": "User context required."},
    }
    candidates = (
        detect_opportunities(
            analytics={
                "benchmark_change_percent": analytics.benchmark_change_percent,
                "sectors": analytics.sectors,
                "breadth": analytics.breadth,
            },
            sector_exposure=exposure,
            snapshots=sectors,
        )
        if user_id > 0
        else []
    )

    as_of = analytics.as_of.isoformat() if analytics.as_of else None
    llm = llm_health()
    public_llm = {
        "enabled": llm.get("enabled"),
        "status": llm.get("status", "disabled"),
        "analysis_available": llm.get("test_successful") or not llm.get("enabled"),
    }
    recent_analyses = _recent_analyses(db, user_id) if user_id > 0 else []
    return {
        "available": True,
        "as_of": as_of,
        "freshness": freshness_label(snaps),
        "source": "nse",
        "is_stale": analytics.is_stale,
        "benchmark": {
            "index_code": analytics.benchmark_code,
            "change_percent": f"{analytics.benchmark_change_percent:.2f}"
            if analytics.benchmark_change_percent is not None
            else None,
        },
        "sectors": analytics.sectors,
        "breadth": analytics.breadth,
        "sector_exposure": exposure,
        "observations": [_candidate_to_observation(c) for c in candidates],
        "llm": public_llm,
        "recent_analyses": recent_analyses,
    }


def _candidate_to_observation(c) -> dict[str, Any]:
    return {
        "type": c.type,
        "sector_index_code": c.sector_index_code,
        "sector_name": c.sector_name,
        "market_move_percent": f"{c.market_move_percent:.2f}" if c.market_move_percent is not None else None,
        "benchmark_move_percent": f"{c.benchmark_move_percent:.2f}" if c.benchmark_move_percent is not None else None,
        "relative_move_percent": f"{c.relative_move_percent:.2f}" if c.relative_move_percent is not None else None,
        "user_exposure_percent": f"{c.user_exposure_percent:.2f}" if c.user_exposure_percent is not None else None,
        "user_exposure_value": f"{c.user_exposure_value:.2f}" if c.user_exposure_value is not None else None,
        "severity": c.severity,
        "reason_codes": c.reason_codes,
    }


def _twin_analysis_context(twin: dict) -> TwinAnalysisContext:
    portfolio = twin.get("portfolio") or {}
    behaviour = twin.get("behaviour") or {}
    return TwinAnalysisContext(
        portfolio={
            "total_value": portfolio.get("total_value"),
            "holdings_count": portfolio.get("holdings_count"),
            "equity_count": portfolio.get("equity_count"),
        },
        goals=[{"name": g.get("name"), "target_amount": g.get("target_amount")} for g in (twin.get("goals") or {}).get("items", [])],
        behavioural={
            "status": behaviour.get("status"),
            "observations": (behaviour.get("observations") or [])[:5],
        },
        completeness=dict(twin.get("completeness") or {}),
        twin_as_of=datetime.now(timezone.utc),
    )


def _opportunity_fingerprint(obs: dict[str, Any]) -> str:
    return "|".join(
        [
            obs.get("type") or "",
            obs.get("sector_index_code") or "",
            obs.get("market_move_percent") or "",
            obs.get("relative_move_percent") or "",
            obs.get("user_exposure_percent") or "",
        ]
    )


def _recent_analyses(db: Session, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
    rows = (
        db.query(MarketOpportunityAnalysis)
        .filter(MarketOpportunityAnalysis.user_id == user_id)
        .order_by(MarketOpportunityAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        payload = row.analysis_json or {}
        out.append(
            {
                "sector_name": payload.get("sector_name"),
                "summary": payload.get("summary"),
                "why_relevant": payload.get("why_relevant"),
                "confidence": row.confidence,
                "source": row.model,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out


def process_user_opportunities(db: Session, user_id: int) -> dict[str, Any]:
    """Detect, analyze, alert — idempotent per fingerprint per day."""
    ctx = build_market_context(db, user_id, force_fetch=True)
    if not ctx.get("available"):
        return {"processed": 0, "items": [], "message": "Market data is temporarily unavailable."}
    observations = ctx.get("observations") or []
    if not observations:
        return {
            "processed": 0,
            "items": [],
            "message": "No material personalized market observations detected.",
        }
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"processed": 0, "items": [], "message": "User not found."}

    twin = twin_svc.assemble_twin(db, user_id)
    twin_ctx = _twin_analysis_context(twin)
    exposure = ctx.get("sector_exposure") or {}
    results = []
    today = datetime.now(timezone.utc).date()

    for obs in observations:
        fingerprint = _opportunity_fingerprint(obs)
        existing = (
            db.query(MarketOpportunity)
            .filter(MarketOpportunity.user_id == user_id)
            .order_by(MarketOpportunity.detected_at.desc())
            .all()
        )
        if any(
            e.detected_at.date() == today and (e.reason_json or {}).get("fingerprint") == fingerprint
            for e in existing
        ):
            continue

        opp = MarketOpportunity(
            user_id=user_id,
            type=obs["type"],
            sector_index_code=obs.get("sector_index_code"),
            sector_name=obs.get("sector_name"),
            detected_at=datetime.now(timezone.utc),
            status="pending_analysis",
            severity=obs.get("severity", "information"),
            reason_json={"reason_codes": obs.get("reason_codes"), "observation": obs, "fingerprint": fingerprint},
        )
        db.add(opp)
        db.flush()

        market_facts = [
            f"{obs.get('sector_name')}: {obs.get('market_move_percent')}% today",
            f"Nifty 50: {obs.get('benchmark_move_percent')}%",
            f"Source: NSE · As of: {ctx.get('as_of')} · Freshness: {ctx.get('freshness')}",
        ]
        if obs.get("relative_move_percent"):
            market_facts.append(f"Relative move: {obs.get('relative_move_percent')} percentage points")
        portfolio_facts = []
        if obs.get("user_exposure_value"):
            portfolio_facts.append(f"Identified exposure: ₹{obs.get('user_exposure_value')}")
        if obs.get("user_exposure_percent"):
            portfolio_facts.append(f"Portfolio weight: {obs.get('user_exposure_percent')}% of equity")

        knowledge = retrieve_knowledge(topics=["sector", "concentration", "diversification", "allocation"])
        from domain.market.contracts import OpportunityCandidate

        candidate = OpportunityCandidate(
            type=obs["type"],
            sector_index_code=obs.get("sector_index_code"),
            sector_name=obs.get("sector_name"),
            market_move_percent=Decimal(obs["market_move_percent"]) if obs.get("market_move_percent") else None,
            benchmark_move_percent=Decimal(obs["benchmark_move_percent"]) if obs.get("benchmark_move_percent") else None,
            relative_move_percent=Decimal(obs["relative_move_percent"]) if obs.get("relative_move_percent") else None,
            user_exposure_percent=Decimal(obs["user_exposure_percent"]) if obs.get("user_exposure_percent") else None,
            user_exposure_value=Decimal(obs["user_exposure_value"]) if obs.get("user_exposure_value") else None,
            reason_codes=obs.get("reason_codes") or [],
            severity=obs.get("severity", "information"),
        )
        sanitized = build_sanitized_analysis_context(
            twin=twin,
            sector_name=obs.get("sector_name"),
            sector_exposure=exposure,
            market_facts=market_facts,
        )
        analysis, analysis_source = analyze_opportunity(
            candidate=candidate,
            twin_context=twin_ctx,
            sanitized_context=sanitized,
            market_facts=market_facts,
            portfolio_facts=portfolio_facts,
            knowledge_refs=knowledge,
        )
        analysis_payload = analysis.to_dict()
        analysis_payload["sector_name"] = obs.get("sector_name")
        opp.status = "analyzed"
        analysis_row = MarketOpportunityAnalysis(
            opportunity_id=opp.id,
            user_id=user_id,
            twin_as_of=twin_ctx.twin_as_of,
            model=analysis_source,
            prompt_version="v1",
            analysis_json=analysis_payload,
            knowledge_refs=knowledge,
            confidence=analysis.confidence,
        )
        db.add(analysis_row)
        db.flush()

        alert = UserAlert(
            user_id=user_id,
            opportunity_analysis_id=analysis_row.id,
            channel="email",
            status="pending",
        )
        db.add(alert)
        db.flush()

        recipient = resolve_notification_recipient(user)
        if recipient:
            subject, body = build_market_observation_email(
                user_name=user.name,
                sector_name=obs.get("sector_name") or "Market",
                sector_change=obs.get("market_move_percent") or "—",
                benchmark_change=obs.get("benchmark_move_percent") or "—",
                relative_change=obs.get("relative_move_percent"),
                exposure_value=obs.get("user_exposure_value"),
                exposure_pct=obs.get("user_exposure_percent"),
                why_surface=analysis.why_relevant,
                analysis_summary=analysis.summary if analysis_source == "litellm" else None,
                missing=analysis.missing_information,
            )
            deliver_alert_email(db, alert, user, subject, body, recipient=recipient)

        results.append(
            {
                "opportunity_id": opp.id,
                "analysis_id": analysis_row.id,
                "alert_id": alert.id,
                "analysis_source": analysis_source,
            }
        )
    if not results:
        return {
            "processed": 0,
            "items": [],
            "message": "No new material personalized market observations detected.",
        }
    return {"processed": len(results), "items": results, "message": "Processed market observations."}
