from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai_cio.db.models import UserJourney
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError

STEPS = (
    "welcome",
    "psychometrics",
    "finances",
    "goals",
    "portfolio",
    "review",
    "analysis",
    "decide",
)
STATUSES = {"not_started", "provided", "skipped"}
DECISIONS = {"accept", "modify", "reject"}


def get_or_create_journey(db: Session, user_id: int) -> UserJourney:
    get_user(db, user_id)
    row = db.query(UserJourney).filter(UserJourney.user_id == user_id).first()
    if row is None:
        row = UserJourney(user_id=user_id, current_step="welcome")
        db.add(row)
        db.flush()
    return row


def set_step(db: Session, user_id: int, step: str) -> UserJourney:
    if step not in STEPS:
        raise DomainError("Unknown journey step")
    row = get_or_create_journey(db, user_id)
    row.current_step = step
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row


def set_status(db: Session, user_id: int, field: str, status: str) -> UserJourney:
    if status not in STATUSES:
        raise DomainError("Status must be not_started, provided, or skipped")
    row = get_or_create_journey(db, user_id)
    if field not in {"finances_status", "goals_status", "portfolio_status"}:
        raise DomainError("Unknown status field")
    setattr(row, field, status)
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row


def record_decision(db: Session, user_id: int, decision: str, notes: str | None = None) -> UserJourney:
    if decision not in DECISIONS:
        raise DomainError("Decision must be accept, modify, or reject")
    row = get_or_create_journey(db, user_id)
    row.decision = decision
    row.decision_notes = notes
    row.current_step = "decide"
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row


def confirm_portfolio(db: Session, user_id: int) -> UserJourney:
    row = get_or_create_journey(db, user_id)
    row.portfolio_status = "provided"
    row.current_step = "review"
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row


def serialize_journey(row: UserJourney) -> dict:
    return {
        "user_id": row.user_id,
        "current_step": row.current_step,
        "finances_status": row.finances_status,
        "goals_status": row.goals_status,
        "portfolio_status": row.portfolio_status,
        "decision": row.decision,
        "decision_notes": row.decision_notes,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
