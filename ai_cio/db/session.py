"""Lazy SQLAlchemy engine so tests can bind a different database."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ai_cio.settings import DATABASE_URL

_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def configure_engine(url: str | None = None, **kwargs) -> Engine:
    global _engine, SessionLocal
    target = url or DATABASE_URL
    options = {"echo": False}
    if not target.startswith("sqlite"):
        options.update(pool_size=10, max_overflow=20)
    options.update({key: value for key, value in kwargs.items() if value is not None})
    _engine = create_engine(target, **options)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        configure_engine()
    assert _engine is not None
    return _engine


def get_session() -> Session:
    if SessionLocal is None:
        configure_engine()
    assert SessionLocal is not None
    return SessionLocal()


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()
