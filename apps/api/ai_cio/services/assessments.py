"""Assessment workflow. Scoring is owned here, never by the client."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai_cio.db.models import AssessmentResponse, AssessmentSession, BehavioralProfile, Instrument, User
from ai_cio.psychometrics.instrument import InstrumentError, apply_answer, instrument_from_payload
from ai_cio.psychometrics.observations import generate_observations
from ai_cio.psychometrics.scoring import AnswerInput, calculate_profile
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError, current_instrument

SCORE_FIELDS = (
    "risk_score",
    "loss_aversion_score",
    "anchoring_score",
    "recency_bias_score",
    "herding_score",
    "overconfidence_score",
    "decision_stability_score",
)


def start_assessment(db: Session, user_id: int) -> AssessmentSession:
    get_user(db, user_id)
    instrument = current_instrument(db)
    session = AssessmentSession(user_id=user_id, instrument_id=instrument.id, status="in_progress")
    db.add(session)
    db.flush()
    return session


def _session(db: Session, session_id: int) -> AssessmentSession:
    row = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if row is None:
        raise DomainError("Assessment session not found")
    return row


def submit_response(
    db: Session,
    session_id: int,
    question_id: str,
    answer_id: str,
    confidence: int,
    response_time_ms: int,
) -> AssessmentResponse:
    session = _session(db, session_id)
    if session.status != "in_progress":
        raise DomainError("Assessment session is not in progress")
    if not (0 <= confidence <= 100):
        raise DomainError("Confidence must be between 0 and 100")
    bank = db.query(Instrument).filter(Instrument.id == session.instrument_id).one()
    instrument = instrument_from_payload(bank.payload)
    try:
        score_applied = apply_answer(instrument, question_id, answer_id)
    except InstrumentError as exc:
        raise DomainError(str(exc)) from exc
    existing = (
        db.query(AssessmentResponse)
        .filter(AssessmentResponse.session_id == session_id, AssessmentResponse.question_id == question_id)
        .first()
    )
    if existing:
        raise DomainError(f"Response already recorded for {question_id}")
    row = AssessmentResponse(
        session_id=session_id,
        question_id=question_id,
        answer_id=answer_id,
        score_applied=score_applied,
        confidence=confidence,
        response_time_ms=response_time_ms,
    )
    db.add(row)
    db.flush()
    return row


def complete_assessment(db: Session, session_id: int) -> BehavioralProfile:
    session = _session(db, session_id)
    if session.status != "in_progress":
        raise DomainError("Assessment is not in progress")
    responses = (
        db.query(AssessmentResponse)
        .filter(AssessmentResponse.session_id == session_id)
        .all()
    )
    if not responses:
        raise DomainError("No responses found for session")
    bank = db.query(Instrument).filter(Instrument.id == session.instrument_id).one()
    instrument = instrument_from_payload(bank.payload)
    answers = [
        AnswerInput(
            question_id=row.question_id,
            answer_id=row.answer_id,
            confidence=row.confidence,
            response_time_ms=row.response_time_ms,
        )
        for row in responses
    ]
    try:
        result = calculate_profile(instrument, answers)
    except InstrumentError as exc:
        raise DomainError(str(exc)) from exc
    profile = BehavioralProfile(
        session_id=session_id,
        user_id=session.user_id,
        instrument_id=session.instrument_id,
        risk_score=result["risk_score"],
        loss_aversion_score=result["loss_aversion_score"],
        anchoring_score=result["anchoring_score"],
        recency_bias_score=result["recency_bias_score"],
        herding_score=result["herding_score"],
        overconfidence_score=result["overconfidence_score"],
        decision_stability_score=result["decision_stability_score"],
        average_confidence=result["average_confidence"],
        average_response_time_ms=result["average_response_time_ms"],
        profile_confidence=result["profile_confidence"],
        polarity=result["polarity"],
    )
    db.add(profile)
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.flush()
    return profile


def get_profile(db: Session, session_id: int) -> BehavioralProfile:
    profile = db.query(BehavioralProfile).filter(BehavioralProfile.session_id == session_id).first()
    if profile is None:
        raise DomainError("Profile not found")
    return profile


def latest_profile(db: Session, user_id: int) -> BehavioralProfile:
    get_user(db, user_id)
    profile = (
        db.query(BehavioralProfile)
        .filter(BehavioralProfile.user_id == user_id)
        .order_by(BehavioralProfile.created_at.desc())
        .first()
    )
    if profile is None:
        raise DomainError("Profile not found")
    return profile


def get_observations(db: Session, session_id: int) -> list[str]:
    profile = get_profile(db, session_id)
    scores = {field: getattr(profile, field) for field in SCORE_FIELDS}
    return generate_observations(scores)


def list_user_assessments(db: Session, user_id: int) -> list[tuple[AssessmentSession, BehavioralProfile | None]]:
    get_user(db, user_id)
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == user_id)
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )
    out = []
    for session in sessions:
        profile = db.query(BehavioralProfile).filter(BehavioralProfile.session_id == session.id).first()
        out.append((session, profile))
    return out


def active_assessment(db: Session, user_id: int) -> dict | None:
    """Return in-progress assessment progress for resume, or None."""
    get_user(db, user_id)
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == user_id, AssessmentSession.status == "in_progress")
        .order_by(AssessmentSession.started_at.desc())
        .first()
    )
    if session is None:
        return None
    answered = (
        db.query(AssessmentResponse)
        .filter(AssessmentResponse.session_id == session.id)
        .count()
    )
    bank = db.query(Instrument).filter(Instrument.id == session.instrument_id).one()
    total = len(bank.payload.get("questions", []))
    return {
        "session_id": session.id,
        "status": session.status,
        "answered_count": answered,
        "total_questions": total,
    }


def admin_stats(db: Session) -> dict:
    total = db.query(AssessmentSession).count()
    completed = db.query(AssessmentSession).filter(AssessmentSession.status == "completed").count()
    return {
        "total_users": db.query(User).count(),
        "total_assessments": total,
        "completed_assessments": completed,
        "in_progress_assessments": total - completed,
    }
