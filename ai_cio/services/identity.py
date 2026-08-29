from __future__ import annotations

from sqlalchemy.orm import Session

from ai_cio.db.models import User, UserJourney
from ai_cio.services.instruments import DomainError
from ai_cio.settings import DEFAULT_USER_ID


def create_user(db: Session, name: str) -> User:
    stripped = name.strip()
    if not stripped:
        raise DomainError("Name is required")
    user = User(name=stripped)
    db.add(user)
    db.flush()
    db.add(UserJourney(user_id=user.id, current_step="psychometrics"))
    db.flush()
    return user


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise DomainError("User not found")
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def resolve_user_id(db: Session, user_id: int | None = None) -> int:
    if user_id is not None:
        get_user(db, user_id)
        return user_id
    if DEFAULT_USER_ID:
        resolved = int(DEFAULT_USER_ID)
        get_user(db, resolved)
        return resolved
    users = db.query(User).all()
    if len(users) == 1:
        return users[0].id
    raise DomainError("user_id is required when multiple users exist; set AICIO_USER_ID or pass user_id")
