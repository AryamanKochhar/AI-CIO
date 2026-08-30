from __future__ import annotations

import hashlib
import secrets

from sqlalchemy.orm import Session

from ai_cio.db.models import User, UserJourney
from ai_cio.services.instruments import DomainError
from ai_cio.settings import DEFAULT_USER_ID

MIN_PASSWORD_LENGTH = 8
_PBKDF2_ITERATIONS = 290_000


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt, stored = password_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    return secrets.compare_digest(digest.hex(), stored)


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _start_journey(db: Session, user_id: int) -> None:
    db.add(UserJourney(user_id=user_id, current_step="psychometrics"))
    db.flush()


def create_user(db: Session, name: str) -> User:
    stripped = name.strip()
    if not stripped:
        raise DomainError("Name is required")
    user = User(name=stripped)
    db.add(user)
    db.flush()
    _start_journey(db, user.id)
    return user


def register_user(db: Session, name: str, email: str, password: str) -> User:
    stripped = name.strip()
    normalised = _normalise_email(email)
    if not stripped:
        raise DomainError("Name is required")
    if not normalised:
        raise DomainError("Email is required")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise DomainError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    existing = db.query(User).filter(User.email == normalised).first()
    if existing is not None:
        raise DomainError("An account with this email already exists")
    user = User(name=stripped, email=normalised, password_hash=_hash_password(password))
    db.add(user)
    db.flush()
    _start_journey(db, user.id)
    return user


def login_user(db: Session, email: str, password: str) -> User:
    normalised = _normalise_email(email)
    user = db.query(User).filter(User.email == normalised).first()
    if user is None or not user.password_hash or not _verify_password(password, user.password_hash):
        raise DomainError("Invalid email or password")
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
