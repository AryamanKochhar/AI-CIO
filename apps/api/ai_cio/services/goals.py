from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ai_cio.db.models import Goal
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError

GOAL_TYPES = {"emergency", "retirement", "education", "home", "vehicle", "travel", "wealth", "other"}
PRIORITIES = {"high", "medium", "low"}
FLEXIBILITY = {"fixed", "somewhat", "flexible"}


def _money(value):
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("Amount must be a number") from exc
    if amount < 0:
        raise DomainError("Amount cannot be negative")
    return amount


def _money_str(value):
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def list_goals(db: Session, user_id: int) -> list[Goal]:
    get_user(db, user_id)
    return db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.id).all()


def create_goal(db: Session, user_id: int, data: dict) -> Goal:
    get_user(db, user_id)
    name = (data.get("name") or "").strip()
    if not name:
        raise DomainError("Goal name is required")
    goal_type = data.get("goal_type") or "other"
    if goal_type not in GOAL_TYPES:
        raise DomainError("Invalid goal type")
    priority = data.get("priority") or "medium"
    if priority not in PRIORITIES:
        raise DomainError("Invalid priority")
    flexibility = data.get("flexibility") or "somewhat"
    if flexibility not in FLEXIBILITY:
        raise DomainError("Invalid flexibility")
    horizon_years = data.get("horizon_years")
    if horizon_years is not None and horizon_years != "":
        try:
            horizon_years = int(horizon_years)
        except (TypeError, ValueError) as exc:
            raise DomainError("horizon_years must be a whole number") from exc
        if horizon_years < 0:
            raise DomainError("horizon_years cannot be negative")
    else:
        horizon_years = None
    row = Goal(
        user_id=user_id,
        name=name,
        goal_type=goal_type,
        target_amount=_money(data.get("target_amount")),
        target_date=(data.get("target_date") or None),
        current_funding=_money(data.get("current_funding")),
        priority=priority,
        flexibility=flexibility,
        horizon_years=horizon_years,
        notes=data.get("notes"),
    )
    db.add(row)
    db.flush()
    return row


def delete_goal(db: Session, user_id: int, goal_id: int) -> None:
    row = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if row is None:
        raise DomainError("Goal not found")
    db.delete(row)
    db.flush()


def serialize_goal(row: Goal) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "goal_type": row.goal_type,
        "target_amount": _money_str(row.target_amount),
        "target_date": row.target_date,
        "current_funding": _money_str(row.current_funding),
        "priority": row.priority,
        "flexibility": row.flexibility,
        "horizon_years": row.horizon_years,
        "notes": row.notes,
    }
