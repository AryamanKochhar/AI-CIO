from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ai_cio.db.models import Goal
from ai_cio.services.identity import get_user
from ai_cio.services.instruments import DomainError

GOAL_TYPES = {"emergency", "retirement", "fire", "education", "home", "vehicle", "travel", "wealth", "other"}
PRIORITIES = {"high", "medium", "low"}
FLEXIBILITY = {"fixed", "somewhat", "flexible"}


def _money(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise DomainError("Amount must be a finite number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("Amount must be a number") from exc
    if not amount.is_finite():
        raise DomainError("Amount must be a finite number")
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


def _goal_values(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise DomainError("Goal name is required")
    goal_type = data.get("goal_type") or "other"
    if goal_type not in GOAL_TYPES:
        raise DomainError("Invalid goal type")
    planning_inputs = data.get("planning_inputs")
    if goal_type == "fire":
        from pydantic import ValidationError
        from ai_cio.api.schemas import FirePlanningInputs
        try:
            planning_inputs = FirePlanningInputs.model_validate(planning_inputs).model_dump(mode="json")
        except ValidationError as exc:
            raise DomainError("A FIRE goal requires valid, explicit planning inputs") from exc
    elif planning_inputs is not None:
        raise DomainError("Planning inputs are only supported for FIRE goals")
    priority = data.get("priority") or "medium"
    if priority not in PRIORITIES:
        raise DomainError("Invalid priority")
    flexibility = data.get("flexibility") or "somewhat"
    if flexibility not in FLEXIBILITY:
        raise DomainError("Invalid flexibility")
    horizon_years = data.get("horizon_years")
    if horizon_years is not None and horizon_years != "":
        try:
            raw_horizon = Decimal(str(horizon_years))
            if isinstance(horizon_years, bool) or not raw_horizon.is_finite() or raw_horizon != raw_horizon.to_integral_value():
                raise ValueError("Non-whole horizon")
            horizon_years = int(raw_horizon)
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise DomainError("horizon_years must be a whole number") from exc
        if horizon_years < 0:
            raise DomainError("horizon_years cannot be negative")
    else:
        horizon_years = None
    if goal_type == "fire":
        horizon_years = planning_inputs["retirement_age"] - planning_inputs["current_age"]
    target_date = data.get("target_date") or None
    if goal_type == "fire" and target_date:
        try:
            target_date = date.fromisoformat(target_date).isoformat()
        except (ValueError, TypeError) as exc:
            raise DomainError("Target date must be an ISO calendar date") from exc
    return dict(
        name=name,
        goal_type=goal_type,
        target_amount=_money(data.get("target_amount")),
        target_date=target_date,
        current_funding=_money(data.get("current_funding")),
        priority=priority,
        flexibility=flexibility,
        horizon_years=horizon_years,
        notes=data.get("notes"),
        planning_inputs=planning_inputs,
    )


def create_goal(db: Session, user_id: int, data: dict) -> Goal:
    get_user(db, user_id)
    row = Goal(user_id=user_id, **_goal_values(data))
    db.add(row)
    db.flush()
    return row


def update_goal(db: Session, user_id: int, goal_id: int, data: dict) -> Goal:
    row = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if row is None:
        raise DomainError("Goal not found")
    # Validate every value before mutating the existing row.
    values = _goal_values(data)
    for key, value in values.items():
        setattr(row, key, value)
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
        "planning_inputs": row.planning_inputs,
    }
