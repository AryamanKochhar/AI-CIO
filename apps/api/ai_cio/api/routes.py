"""HTTP adapter over the canonical domain layer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ai_cio.api.schemas import (
    AssessmentSessionCreate,
    AssessmentSessionResponse,
    AssessmentSummary,
    FinancesUpdate,
    GoalCreate,
    JourneyUpdate,
    LoginRequest,
    ProfileResponse,
    RegisterRequest,
    ResponseCreate,
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
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services import review as review_svc
from ai_cio.services import twin as twin_svc
from ai_cio.services.instruments import DomainError

router = APIRouter()


def _http(exc: DomainError) -> HTTPException:
    detail = str(exc)
    status = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status, detail=detail)


@router.get("/health")
def health_check():
    return {"status": "ok"}


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
        if kind == "cas_pdf" and info["holdings"] > 0:
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
        for key in ("closing_units", "nav", "valuation"):
            item[key] = f"{item[key]:.2f}"
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
