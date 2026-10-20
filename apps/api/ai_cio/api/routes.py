"""HTTP adapter over the canonical domain layer."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from ai_cio.api.schemas import (
    AssessmentSessionCreate,
    AssessmentSessionResponse,
    AssessmentSummary,
    FinancesUpdate,
    FirePlanningInputs,
    FixedDepositCreate,
    GoalCreate,
    JourneyUpdate,
    LoginRequest,
    ProfileResponse,
    RegisterRequest,
    ResponseCreate,
    DecisionRequestBody,
    ReviewDecision,
    UserCreate,
    UserResponse,
)
from ai_cio.db.models import AssessmentSession, BehavioralProfile, User
from ai_cio.db.session import get_db
from ai_cio.services import assessments as assessment_svc
from ai_cio.services import documents as document_svc
from ai_cio.services import finances as finance_svc
from ai_cio.services import goals as goal_svc
from ai_cio.services import identity as identity_svc
from ai_cio.services import instruments as instrument_svc
from ai_cio.services import journey as journey_svc
from ai_cio.services import market_context as market_context_svc
from ai_cio.services import news as news_svc
from ai_cio.services import news_ai as news_ai_svc
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services import review as review_svc
from ai_cio.services import twin as twin_svc
from ai_cio.services import health as health_svc
from ai_cio.services.orchestration import run_decision
from ai_cio.services.decision_cache import (
    get_latest_cached_decision,
    run_cached_decision,
)
from ai_cio.services.instruments import DomainError
from ai_cio.services.agents.tax_agent import run_tax_agent
from ai_cio.services.agents.fd_agent import run_fd_agent
from ai_cio.services.fd.holdings import create_fixed_deposit, delete_fixed_deposit, list_fixed_deposits
from ai_cio.services.fd.rates import get_fd_rates
from ai_cio.services.trajectory import run_trajectory_for_user
from domain.decision.contracts import DecisionRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users/{user_id}/mutual-funds")
def get_mutual_fund_intelligence(user_id: int, response: Response, db: Session = Depends(get_db)):
    from ai_cio.services.agents.mutual_fund_agent import run_mutual_fund_agent
    response.headers["Cache-Control"] = "private, no-store"
    try:
        identity_svc.get_user(db, user_id)
        twin = twin_svc.assemble_twin(db, user_id)
        twin["portfolio"]["transactions"] = portfolio_svc.list_transactions(db, user_id)
        twin["portfolio"]["transactions_complete"] = False
        return run_mutual_fund_agent(twin)
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/bonds")
def get_bond_intelligence(user_id: int, response: Response, db: Session = Depends(get_db)):
    from ai_cio.services.agents.bond_agent import run_bond_agent
    from ai_cio.services.orchestration.policy import contribution_policy
    from ai_cio.services.bond_action_checks import reconcile_bond_action_checks
    response.headers["Cache-Control"] = "private, no-store"
    try:
        identity_svc.get_user(db, user_id)
        twin = twin_svc.assemble_twin(db, user_id)
        twin["contribution_policy"] = contribution_policy(twin, {})
        result = run_bond_agent(twin)
        result["central_checks"] = reconcile_bond_action_checks(result, twin["contribution_policy"], twin.get("decision_constraints"))
        return result
    except DomainError as exc:
        raise _http(exc) from exc


def _import_mutual_fund_evidence(user_id: int, payload: dict, db: Session, *, benchmark: bool):
    import json
    import os
    from ai_cio.services.mutual_funds.disclosures import import_benchmark, import_disclosure
    from ai_cio.services.mutual_funds.provider import DEFAULT_CACHE_DIR
    try:
        identity_svc.get_user(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc
    if len(json.dumps(payload).encode()) > 2_000_000:
        raise HTTPException(status_code=413, detail="Evidence upload exceeds 2 MB")
    importer = import_benchmark if benchmark else import_disclosure
    try:
        return importer(payload, cache_dir=os.getenv("MUTUAL_FUND_CACHE_DIR") or DEFAULT_CACHE_DIR, user_id=user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/users/{user_id}/mutual-funds/disclosures")
def import_mutual_fund_disclosure(user_id: int, payload: dict, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return _import_mutual_fund_evidence(user_id, payload, db, benchmark=False)


@router.post("/users/{user_id}/mutual-funds/benchmarks")
def import_mutual_fund_benchmark(user_id: int, payload: dict, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return _import_mutual_fund_evidence(user_id, payload, db, benchmark=True)


@router.get("/knowledge/principles/{principle_id}")
def get_applied_principle(principle_id: str):
    from ai_cio.services.skill_principles import resolve_principle
    principle = resolve_principle(principle_id)
    if principle is None:
        raise HTTPException(status_code=404, detail="Verified skill principle not found")
    return principle


@router.get("/demo/personas")
def get_demo_personas(db: Session = Depends(get_db)):
    from ai_cio.services.demo_personas import persona_catalogue

    try:
        return {"personas": persona_catalogue(db)}
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/demo/personas/{persona_id}/launch")
def launch_demo_persona(persona_id: str, db: Session = Depends(get_db)):
    from ai_cio.services.demo_personas import launch_persona

    try:
        result = launch_persona(db, persona_id)
        db.commit()
        result["user"] = UserResponse.model_validate(result["user"])
        return result
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


def _http(exc: DomainError) -> HTTPException:
    detail = str(exc)
    status = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status, detail=detail)


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    return health_svc.build_health_payload(db)


@router.get("/health/llm")
def llm_health_check():
    from ai_cio.services.llm_provider import llm_health

    return llm_health()


@router.post("/auth/register", response_model=UserResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    try:
        row = identity_svc.register_user(db, body.name, body.email, body.password)
        db.commit()
        db.refresh(row)
        return row
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/auth/login", response_model=UserResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        row = identity_svc.login_user(db, body.email, body.password)
        db.commit()
        return row
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/instruments/current")
def get_current_instrument(db: Session = Depends(get_db)):
    try:
        row = instrument_svc.current_instrument(db)
    except DomainError as exc:
        raise _http(exc) from exc
    return {"id": row.id, "version": row.version}


@router.get("/instruments/current/questions")
def get_current_questions(db: Session = Depends(get_db)):
    try:
        return instrument_svc.public_questions(db)
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        row = identity_svc.create_user(db, user.name)
        db.commit()
        db.refresh(row)
        return row
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    try:
        return identity_svc.get_user(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/assessments/start", response_model=AssessmentSessionResponse)
def start_assessment(session_data: AssessmentSessionCreate, db: Session = Depends(get_db)):
    try:
        row = assessment_svc.start_assessment(db, session_data.user_id)
        db.commit()
        db.refresh(row)
        return row
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/assessments/{session_id}", response_model=AssessmentSessionResponse)
def get_assessment(session_id: int, db: Session = Depends(get_db)):
    row = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    return row


@router.post("/assessments/{session_id}/responses")
def submit_response(session_id: int, response_data: ResponseCreate, db: Session = Depends(get_db)):
    try:
        row = assessment_svc.submit_response(
            db,
            session_id,
            response_data.question_id,
            response_data.answer,
            response_data.confidence,
            response_data.response_time_ms,
        )
        db.commit()
        return {"id": row.id, "status": "recorded", "question_id": row.question_id}
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/assessments/{session_id}/complete", response_model=ProfileResponse)
def complete_assessment(session_id: int, db: Session = Depends(get_db)):
    try:
        profile = assessment_svc.complete_assessment(db, session_id)
        db.commit()
        db.refresh(profile)
        return profile
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/assessments/{session_id}/profile", response_model=ProfileResponse)
def get_profile(session_id: int, db: Session = Depends(get_db)):
    try:
        return assessment_svc.get_profile(db, session_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/assessments/{session_id}/observations")
def get_observations(session_id: int, db: Session = Depends(get_db)):
    try:
        return {"session_id": session_id, "observations": assessment_svc.get_observations(db, session_id)}
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/profile", response_model=ProfileResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    try:
        return assessment_svc.latest_profile(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/assessments", response_model=list[AssessmentSummary])
def get_user_assessments(user_id: int, db: Session = Depends(get_db)):
    try:
        pairs = assessment_svc.list_user_assessments(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc
    summaries = []
    for session, profile in pairs:
        summaries.append(
            AssessmentSummary(
                id=session.id,
                started_at=session.started_at,
                completed_at=session.completed_at,
                status=session.status,
                risk_score=profile.risk_score if profile else None,
                created_at=profile.created_at if profile else None,
            )
        )
    return summaries


@router.post("/users/{user_id}/documents/cas")
async def upload_cas(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="A PDF file is required")
    payload = await file.read()
    try:
        document, info = document_svc.ingest_uploaded_document(
            db, user_id, "cas_pdf", file.filename, payload
        )
        journey_svc.set_status(db, user_id, "portfolio_status", "provided")
        db.commit()
        db.refresh(document)
        return {
            "document_id": document.id,
            "user_id": document.user_id,
            "kind": document.kind,
            "filename": document.filename,
            "status": document.status,
            "holdings": info["holdings"],
            "transactions": info["transactions"],
            "warnings": info["warnings"],
            "parser_pending": info["parser_pending"],
        }
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/users/{user_id}/documents")
async def upload_document(
    user_id: int,
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file is required")
    payload = await file.read()
    try:
        document, info = document_svc.ingest_uploaded_document(
            db, user_id, kind, file.filename, payload
        )
        if kind in {"cas_pdf", "cdsl_statement"} and info.get("holdings", 0) > 0:
            journey_svc.set_status(db, user_id, "portfolio_status", "provided")
        db.commit()
        db.refresh(document)
        return {
            "document_id": document.id,
            "user_id": document.user_id,
            "kind": document.kind,
            "filename": document.filename,
            "status": document.status,
            "validation_status": document.validation_status,
            "holdings": info["holdings"],
            "transactions": info["transactions"],
            "warnings": info["warnings"],
            "parser_pending": info["parser_pending"],
            "already_processed": info.get("already_processed", False),
            "summary": info.get("summary"),
            "statement_period": info.get("statement_period"),
            "successful_sections": info.get("successful_sections"),
            "failed_sections": info.get("failed_sections"),
            "metadata": (document.metadata_json or None),
        }
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/holdings")
def get_user_holdings(user_id: int, document_id: int | None = None, db: Session = Depends(get_db)):
    try:
        rows = portfolio_svc.list_holdings(db, user_id, document_id)
    except DomainError as exc:
        raise _http(exc) from exc
    serialised = []
    for row in rows:
        item = dict(row)
        for key in ("closing_units", "nav", "valuation", "invested_amount", "unrealised_pl", "unrealised_pl_pct"):
            if item.get(key) is not None:
                item[key] = f"{item[key]:.2f}" if key != "closing_units" else f"{item[key]:.4f}"
        serialised.append(item)
    return serialised


@router.get("/users/{user_id}/transactions")
def get_user_transactions(user_id: int, document_id: int | None = None, db: Session = Depends(get_db)):
    try:
        rows = portfolio_svc.list_transactions(db, user_id, document_id)
    except DomainError as exc:
        raise _http(exc) from exc
    serialised = []
    for row in rows:
        item = dict(row)
        for key in ("amount", "units", "nav", "unit_balance"):
            if item.get(key) is not None:
                item[key] = f"{item[key]:.2f}"
        serialised.append(item)
    return serialised


@router.get("/users/{user_id}/news")
def get_user_news(user_id: int, db: Session = Depends(get_db)):
    try:
        payload = news_svc.get_portfolio_news(db, user_id)
        if payload.get("available"):
            twin = twin_svc.assemble_twin(db, user_id)
            payload = news_ai_svc.enrich_news_with_profile_impact(payload, twin=twin)
        else:
            payload["profile_impact"] = {
                "used": False,
                "reason": payload.get("reason") or "No news to analyze against your profile.",
            }
        return payload
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/documents")
def get_user_documents(user_id: int, db: Session = Depends(get_db)):
    try:
        rows = document_svc.list_documents(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc
    return [document_svc.serialize_document(row) for row in rows]


@router.get("/users/{user_id}/twin")
def get_twin(user_id: int, db: Session = Depends(get_db)):
    try:
        return twin_svc.assemble_twin(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/decisions")
def create_decision(user_id: int, body: DecisionRequestBody, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        request = DecisionRequest.from_payload(
            user_id=user_id,
            objective=body.objective,
            available_capital=body.available_capital,
            constraints=body.constraints,
            requested_action=body.requested_action,
        )
        return run_cached_decision(db, request, compute=run_decision, force_refresh=body.force_refresh)
    except DomainError as exc:
        raise _http(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("create_decision_failed user_id=%s objective=%s", user_id, body.objective)
        raise HTTPException(
            status_code=500,
            detail=f"Decision failed: {exc}",
        ) from exc


@router.get("/users/{user_id}/decisions/cached")
def get_cached_decision_result(
    user_id: int,
    response: Response,
    objective: str | None = None,
    db: Session = Depends(get_db),
):
    """Return only a fresh decision whose authoritative inputs still match."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        payload = get_latest_cached_decision(db, user_id=user_id, objective=objective)
        if payload is None:
            return {"available": False, "stale": False, "reason": "No cached decision yet."}
        if payload.get("stale"):
            return payload
        return {"available": True, "stale": False, "result": payload}
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/decisions/trajectory")
def get_trajectory(
    user_id: int,
    horizon_years: int = 20,
    include_liquid: bool = False,
    db: Session = Depends(get_db),
):
    try:
        return run_trajectory_for_user(
            db,
            user_id,
            constraints={
                "projection_horizon_years": horizon_years,
                "include_liquid_in_projection": include_liquid,
            },
        )
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/decisions/what-if")
def post_trajectory_what_if(user_id: int, body: dict, db: Session = Depends(get_db)):
    try:
        constraints = dict(body or {})
        what_if = {
            "monthly_contribution": constraints.pop("monthly_contribution", None),
            "annual_return_percent": constraints.pop("annual_return_percent", None),
            "horizon_years": constraints.pop("horizon_years", 15),
            "contribution_growth_pa": constraints.pop("contribution_growth_pa", None),
        }
        constraints["what_if"] = what_if
        return run_trajectory_for_user(db, user_id, constraints=constraints)
    except DomainError as exc:
        raise _http(exc) from exc


def _with_skill_review(db: Session, user_id: int, payload: dict, owner: str) -> dict:
    from ai_cio.services.grounded_reviews import build_grounded_reviews
    if not payload.get("available"):
        return {**payload, "review_findings": []}
    twin = {"financial_position": {"fixed_deposits": {"items": payload.get("fixed_deposits") or []}}} if owner == "fd_agent" else {}
    checked = build_grounded_reviews(twin, {"specialist_checks": {"tax": payload if owner == "tax_agent" else {}}})
    return {**payload, "review_findings": [row for row in checked["items"] if row["owner"] == owner]}


@router.get("/users/{user_id}/tax/summary")
def get_tax_summary(user_id: int, financial_year: str | None = None, db: Session = Depends(get_db)):
    try:
        payload = run_tax_agent(db, user_id, financial_year=financial_year)
        return _with_skill_review(db, user_id, payload, "tax_agent")
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/tax/opportunities")
def get_tax_opportunities(user_id: int, financial_year: str | None = None, db: Session = Depends(get_db)):
    try:
        payload = run_tax_agent(db, user_id, financial_year=financial_year)
        return {
            "available": payload.get("available"),
            "financial_year": payload.get("financial_year"),
            "opportunities": payload.get("opportunities") or [],
            "holding_period_events": payload.get("holding_period_events") or [],
            "disclaimer": payload.get("disclaimer"),
        }
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/tax/lots")
def get_tax_lots(user_id: int, financial_year: str | None = None, db: Session = Depends(get_db)):
    try:
        payload = run_tax_agent(db, user_id, financial_year=financial_year)
        return {
            "available": payload.get("available"),
            "financial_year": payload.get("financial_year"),
            "rule_version": payload.get("rule_version"),
            "tax_lots": payload.get("tax_lots") or {},
            "missing_data": payload.get("missing_data") or [],
            "data_quality": payload.get("data_quality") or {},
            "disclaimer": payload.get("disclaimer"),
        }
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/tax/capital-gains")
def get_tax_capital_gains(user_id: int, financial_year: str | None = None, db: Session = Depends(get_db)):
    try:
        payload = run_tax_agent(db, user_id, financial_year=financial_year)
        return {
            "available": payload.get("available"),
            "financial_year": payload.get("financial_year"),
            "rule_version": payload.get("rule_version"),
            "summary": payload.get("summary") or {},
            "by_security": payload.get("by_security") or [],
            "tax_estimate": payload.get("tax_estimate") or {},
            "disclaimer": payload.get("disclaimer"),
        }
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/tax/losses")
def get_tax_losses(user_id: int, financial_year: str | None = None, db: Session = Depends(get_db)):
    try:
        payload = run_tax_agent(db, user_id, financial_year=financial_year)
        return {
            "available": payload.get("available"),
            "financial_year": payload.get("financial_year"),
            "loss_inventory": payload.get("loss_inventory") or {},
            "opportunities": [
                o
                for o in (payload.get("opportunities") or [])
                if o.get("type") in {"tax_loss_harvesting", "loss_utilization"}
            ],
            "disclaimer": payload.get("disclaimer"),
        }
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/fd/summary")
def get_fd_summary(user_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    try:
        payload = run_fd_agent(db, user_id, force_refresh_rates=refresh)
        return _with_skill_review(db, user_id, payload, "fd_agent")
    except DomainError as exc:
        raise _http(exc) from exc


@router.get("/users/{user_id}/fd/rates")
def get_user_fd_rates(user_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    try:
        # Ensure user exists
        from ai_cio.services.identity import get_user

        get_user(db, user_id)
        payload = get_fd_rates(db, force_refresh=refresh)
        db.commit()
        return payload
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/fd/holdings")
def get_fd_holdings(user_id: int, db: Session = Depends(get_db)):
    try:
        return {"items": list_fixed_deposits(db, user_id)}
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/fd/holdings")
def post_fd_holding(user_id: int, body: FixedDepositCreate, db: Session = Depends(get_db)):
    try:
        row = create_fixed_deposit(db, user_id, body.model_dump())
        db.commit()
        return row
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.delete("/users/{user_id}/fd/holdings/{fd_id}")
def remove_fd_holding(user_id: int, fd_id: int, db: Session = Depends(get_db)):
    try:
        delete_fixed_deposit(db, user_id, fd_id)
        db.commit()
        return {"ok": True}
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/market/snapshot")
def get_market_snapshot(db: Session = Depends(get_db)):
    try:
        return market_context_svc.build_public_market_snapshot(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Market data temporarily unavailable") from exc


@router.get("/users/{user_id}/market-context")
def get_user_market_context(user_id: int, db: Session = Depends(get_db)):
    try:
        identity_svc.get_user(db, user_id)
        return market_context_svc.build_market_context(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/market/process")
def process_market_opportunities(user_id: int, db: Session = Depends(get_db)):
    try:
        identity_svc.get_user(db, user_id)
        result = market_context_svc.process_user_opportunities(db, user_id)
        db.commit()
        return result
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/finances")
def get_finances(user_id: int, db: Session = Depends(get_db)):
    try:
        return finance_svc.serialize_finances(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.put("/users/{user_id}/finances")
def put_finances(user_id: int, body: FinancesUpdate, db: Session = Depends(get_db)):
    try:
        if body.skipped:
            journey_svc.set_status(db, user_id, "finances_status", "skipped")
        else:
            finance_svc.replace_finances(
                db,
                user_id,
                income=body.income,
                expenses=body.expenses,
                liquid=body.liquid,
                cadence=body.cadence,
                liabilities=body.liabilities,
            )
            journey_svc.set_status(db, user_id, "finances_status", "provided")
        db.commit()
        return finance_svc.serialize_finances(db, user_id)
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/goals")
def get_goals(user_id: int, db: Session = Depends(get_db)):
    try:
        return [goal_svc.serialize_goal(row) for row in goal_svc.list_goals(db, user_id)]
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/goals")
def post_goal(user_id: int, body: GoalCreate, db: Session = Depends(get_db)):
    try:
        row = goal_svc.create_goal(db, user_id, body.model_dump())
        journey_svc.set_status(db, user_id, "goals_status", "provided")
        db.commit()
        db.refresh(row)
        return goal_svc.serialize_goal(row)
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.put("/users/{user_id}/goals/{goal_id}")
def update_goal(user_id: int, goal_id: int, body: GoalCreate, db: Session = Depends(get_db)):
    try:
        row = goal_svc.update_goal(db, user_id, goal_id, body.model_dump())
        db.commit()
        db.refresh(row)
        return goal_svc.serialize_goal(row)
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/users/{user_id}/fire/preview")
def preview_fire_plan(user_id: int, body: FirePlanningInputs, response: Response, db: Session = Depends(get_db)):
    from ai_cio.services.fire_planner import build_fire_plan
    response.headers["Cache-Control"] = "private, no-store"
    try:
        twin = twin_svc.assemble_twin(db, user_id)
        return build_fire_plan(twin, body.model_dump(mode="json"))
    except DomainError as exc:
        raise _http(exc) from exc


@router.delete("/users/{user_id}/goals/{goal_id}")
def remove_goal(user_id: int, goal_id: int, db: Session = Depends(get_db)):
    try:
        goal_svc.delete_goal(db, user_id, goal_id)
        if not goal_svc.list_goals(db, user_id):
            journey_svc.set_status(db, user_id, "goals_status", "not_started")
        db.commit()
        return {"status": "deleted"}
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/users/{user_id}/goals/skip")
def skip_goals(user_id: int, db: Session = Depends(get_db)):
    try:
        journey_svc.set_status(db, user_id, "goals_status", "skipped")
        db.commit()
        return journey_svc.serialize_journey(journey_svc.get_or_create_journey(db, user_id))
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/journey")
def get_journey(user_id: int, db: Session = Depends(get_db)):
    try:
        return journey_svc.serialize_journey(journey_svc.get_or_create_journey(db, user_id))
    except DomainError as exc:
        raise _http(exc) from exc


@router.put("/users/{user_id}/journey")
def put_journey(user_id: int, body: JourneyUpdate, db: Session = Depends(get_db)):
    try:
        if body.current_step:
            journey_svc.set_step(db, user_id, body.current_step)
        for field in ("finances_status", "goals_status", "portfolio_status"):
            value = getattr(body, field)
            if value:
                journey_svc.set_status(db, user_id, field, value)
        db.commit()
        return journey_svc.serialize_journey(journey_svc.get_or_create_journey(db, user_id))
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/assessments/active")
def get_active_assessment(user_id: int, db: Session = Depends(get_db)):
    try:
        active = assessment_svc.active_assessment(db, user_id)
        if active is None:
            return {"active": False}
        return {"active": True, **active}
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/portfolio/confirm")
def confirm_portfolio(user_id: int, db: Session = Depends(get_db)):
    try:
        row = journey_svc.confirm_portfolio(db, user_id)
        db.commit()
        return journey_svc.serialize_journey(row)
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/users/{user_id}/review")
def get_review(user_id: int, db: Session = Depends(get_db)):
    try:
        return review_svc.assemble_review(db, user_id)
    except DomainError as exc:
        raise _http(exc) from exc


@router.post("/users/{user_id}/review-decision")
def post_review_decision(user_id: int, body: ReviewDecision, db: Session = Depends(get_db)):
    try:
        row = journey_svc.record_decision(db, user_id, body.decision, body.notes)
        db.commit()
        return journey_svc.serialize_journey(row)
    except DomainError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    return assessment_svc.admin_stats(db)


@router.get("/admin/users", response_model=list[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    return identity_svc.list_users(db)


@router.get("/admin/assessments")
def get_all_assessments(db: Session = Depends(get_db)):
    sessions = db.query(AssessmentSession).order_by(AssessmentSession.started_at.desc()).all()
    out = []
    for session in sessions:
        user = db.query(User).filter(User.id == session.user_id).first()
        profile = db.query(BehavioralProfile).filter(BehavioralProfile.session_id == session.id).first()
        out.append(
            {
                "id": session.id,
                "user_id": session.user_id,
                "user_name": user.name if user else "Unknown",
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "status": session.status,
                "risk_score": profile.risk_score if profile else None,
                "profile_confidence": profile.profile_confidence if profile else None,
            }
        )
    return out
