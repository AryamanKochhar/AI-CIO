"""API routes for the psychometric assessment system."""
from fastapi import APIRouter, Depends, HTTPException
from backend.schemas import AssessmentSessionCreate
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from backend.database import get_db
from backend.models import User, AssessmentSession, Response, Profile, AssessmentStatus
from backend.schemas import (
    UserCreate,
    UserResponse,
    AssessmentSessionResponse,
    ResponseCreate,
    ProfileResponse,
    AssessmentSummary,
)
from backend.scoring import BehavioralScorer

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ============================================================================
# USER ENDPOINTS
# ============================================================================


@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.

    Args:
        user: User creation schema with name
        db: Database session

    Returns:
        Created user object
    """
    db_user = User(name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a user by ID."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


# ============================================================================
# ASSESSMENT SESSION ENDPOINTS
# ============================================================================


@router.post("/assessments/start", response_model=AssessmentSessionResponse)
async def start_assessment(
    session_data: AssessmentSessionCreate, db: Session = Depends(get_db)
):
    """
    Start a new assessment session for a user.

    Args:
        session_data: Session creation schema with user_id
        db: Database session

    Returns:
        Created assessment session object
    """
    # Verify user exists
    db_user = db.query(User).filter(User.id == session_data.user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create new assessment session
    db_session = AssessmentSession(
        user_id=session_data.user_id,
        status=AssessmentStatus.IN_PROGRESS,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@router.get("/assessments/{session_id}", response_model=AssessmentSessionResponse)
async def get_assessment(session_id: int, db: Session = Depends(get_db)):
    """Get an assessment session by ID."""
    db_session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id
    ).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    return db_session


# ============================================================================
# RESPONSE ENDPOINTS
# ============================================================================


@router.post("/assessments/{session_id}/responses")
async def submit_response(
    session_id: int,
    response_data: ResponseCreate,
    db: Session = Depends(get_db),
):
    """
    Store a single response for an assessment.

    Args:
        session_id: Assessment session ID
        response_data: Response with question_id, answer, confidence, response_time_ms
        db: Database session

    Returns:
        Created response object
    """
    # Verify session exists and is in progress
    db_session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id
    ).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Assessment session not found")

    if db_session.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400, detail="Assessment session is not in progress"
        )

    # Validate confidence is 0-100
    if not (0 <= response_data.confidence <= 100):
        raise HTTPException(
            status_code=400, detail="Confidence must be between 0 and 100"
        )

    # Create response
    db_response = Response(
        session_id=session_id,
        question_id=response_data.question_id,
        answer=response_data.answer,
        confidence=response_data.confidence,
        response_time_ms=response_data.response_time_ms,
    )
    db.add(db_response)
    db.commit()
    db.refresh(db_response)
    return {"id": db_response.id, "status": "recorded"}


# ============================================================================
# ASSESSMENT COMPLETION ENDPOINTS
# ============================================================================


@router.post("/assessments/{session_id}/complete")
async def complete_assessment(session_id: int, db: Session = Depends(get_db)):
    """
    Complete an assessment session and generate behavioral profile.

    Args:
        session_id: Assessment session ID
        db: Database session

    Returns:
        Generated profile
    """
    # Verify session exists
    db_session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id
    ).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Assessment session not found")

    if db_session.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Assessment is not in progress")

    try:
        # Calculate behavioral profile
        profile_scores = BehavioralScorer.calculate_profile(session_id, db)

        # Create profile record
        profile = Profile(
            session_id=session_id,
            user_id=db_session.user_id,
            risk_score=profile_scores["risk_score"],
            loss_aversion_score=profile_scores["loss_aversion_score"],
            anchoring_score=profile_scores["anchoring_score"],
            recency_bias_score=profile_scores["recency_bias_score"],
            herding_score=profile_scores["herding_score"],
            overconfidence_score=profile_scores["overconfidence_score"],
            decision_stability_score=profile_scores["decision_stability_score"],
            average_confidence=profile_scores["average_confidence"],
            average_response_time_ms=profile_scores["average_response_time_ms"],
            profile_confidence=profile_scores["profile_confidence"],
        )
        db.add(profile)

        # Update session status
        db_session.status = AssessmentStatus.COMPLETED
        db_session.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(profile)

        return profile

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/assessments/{session_id}/profile", response_model=ProfileResponse)
async def get_profile(session_id: int, db: Session = Depends(get_db)):
    """
    Get the behavioral profile for a completed assessment.

    Args:
        session_id: Assessment session ID
        db: Database session

    Returns:
        Profile object
    """
    profile = db.query(Profile).filter(Profile.session_id == session_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/assessments/{session_id}/observations")
async def get_observations(session_id: int, db: Session = Depends(get_db)):
    """
    Get textual observations about a behavioral profile.

    Args:
        session_id: Assessment session ID
        db: Database session

    Returns:
        Dictionary with observations
    """
    profile = db.query(Profile).filter(Profile.session_id == session_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    scores = {
        "risk_score": profile.risk_score,
        "loss_aversion_score": profile.loss_aversion_score,
        "anchoring_score": profile.anchoring_score,
        "recency_bias_score": profile.recency_bias_score,
        "herding_score": profile.herding_score,
        "overconfidence_score": profile.overconfidence_score,
        "decision_stability_score": profile.decision_stability_score,
    }

    observations = BehavioralScorer.generate_observations(scores)

    return {
        "session_id": session_id,
        "observations": observations,
    }


# ============================================================================
# HISTORY ENDPOINTS
# ============================================================================


@router.get("/users/{user_id}/assessments", response_model=List[AssessmentSummary])
async def get_user_assessments(user_id: int, db: Session = Depends(get_db)):
    """
    Get all assessment sessions for a user.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        List of assessment summaries
    """
    # Verify user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all sessions with their profiles
    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id
    ).order_by(AssessmentSession.started_at.desc()).all()

    summaries = []
    for session in sessions:
        profile = db.query(Profile).filter(Profile.session_id == session.id).first()
        summaries.append(
            AssessmentSummary(
                id=session.id,
                started_at=session.started_at,
                completed_at=session.completed_at,
                status=session.status.value,
                risk_score=profile.risk_score if profile else None,
                created_at=profile.created_at if profile else None,
            )
        )

    return summaries


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@router.get("/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    """
    Get basic admin statistics.

    Returns:
        Dictionary with user and assessment counts
    """
    user_count = db.query(User).count()
    session_count = db.query(AssessmentSession).count()
    completed_count = db.query(AssessmentSession).filter(
        AssessmentSession.status == AssessmentStatus.COMPLETED
    ).count()

    return {
        "total_users": user_count,
        "total_assessments": session_count,
        "completed_assessments": completed_count,
        "in_progress_assessments": session_count - completed_count,
    }


@router.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(db: Session = Depends(get_db)):
    """Get all users (admin view)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.get("/admin/assessments")
async def get_all_assessments(db: Session = Depends(get_db)):
    """Get all assessments (admin view)."""
    sessions = db.query(AssessmentSession).order_by(
        AssessmentSession.started_at.desc()
    ).all()

    assessments = []
    for session in sessions:
        user = db.query(User).filter(User.id == session.user_id).first()
        profile = db.query(Profile).filter(Profile.session_id == session.id).first()
        assessments.append(
            {
                "id": session.id,
                "user_id": session.user_id,
                "user_name": user.name if user else "Unknown",
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "status": session.status.value,
                "risk_score": profile.risk_score if profile else None,
                "profile_confidence": profile.profile_confidence if profile else None,
            }
        )

    return assessments
