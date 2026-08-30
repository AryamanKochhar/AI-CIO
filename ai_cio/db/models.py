"""Canonical Postgres models. Monetary columns are Numeric, never Float."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_cio.db.base import Base

JSONBCompat = JSON().with_variant(JSONB(), "postgresql")

DOCUMENT_KINDS = frozenset({"cas_pdf", "nsdl_statement", "cdsl_statement", "other"})
DOCUMENT_STATUSES = frozenset({"pending", "processing", "extracted", "needs_review", "failed"})
VALIDATION_STATUSES = frozenset({"unvalidated", "valid", "partial", "invalid"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    assessment_sessions = relationship("AssessmentSession", back_populates="user")
    documents = relationship("Document", back_populates="user")
    profiles = relationship("BehavioralProfile", back_populates="user")


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONBCompat, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    sessions = relationship("AssessmentSession", back_populates="instrument")


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_assessment_sessions_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="assessment_sessions")
    instrument = relationship("Instrument", back_populates="sessions")
    responses = relationship("AssessmentResponse", back_populates="session", cascade="all, delete-orphan")
    profile = relationship("BehavioralProfile", back_populates="session", uselist=False, cascade="all, delete-orphan")


class AssessmentResponse(Base):
    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_assessment_responses_session_question"),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="ck_assessment_responses_confidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_id: Mapped[str] = mapped_column(String(32), nullable=False)
    score_applied: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    session = relationship("AssessmentSession", back_populates="responses")


class BehavioralProfile(Base):
    __tablename__ = "behavioral_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    loss_aversion_score: Mapped[float] = mapped_column(Float, nullable=False)
    anchoring_score: Mapped[float] = mapped_column(Float, nullable=False)
    recency_bias_score: Mapped[float] = mapped_column(Float, nullable=False)
    herding_score: Mapped[float] = mapped_column(Float, nullable=False)
    overconfidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    decision_stability_score: Mapped[float] = mapped_column(Float, nullable=False)

    average_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    average_response_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    profile_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    polarity: Mapped[dict] = mapped_column(JSONBCompat, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    session = relationship("AssessmentSession", back_populates="profile")
    user = relationship("User", back_populates="profiles")
    instrument = relationship("Instrument")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'extracted', 'needs_review', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "validation_status IS NULL OR validation_status IN ('unvalidated', 'valid', 'partial', 'invalid')",
            name="ck_documents_validation_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="cas_pdf")
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    warning_json: Mapped[list | dict | None] = mapped_column(JSONBCompat, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    validation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="documents")
    source_pages = relationship("SourcePage", back_populates="document", cascade="all, delete-orphan")
    funds = relationship("Fund", back_populates="document", cascade="all, delete-orphan")


class SourcePage(Base):
    __tablename__ = "source_pages"
    __table_args__ = (UniqueConstraint("document_id", "page", name="uq_source_pages_document_page"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document = relationship("Document", back_populates="source_pages")


class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "amc", "folio", "scheme_name", "isin",
            name="uq_funds_document_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    amc: Mapped[str] = mapped_column(Text, nullable=False)
    folio: Mapped[str] = mapped_column(Text, nullable=False)
    scheme_name: Mapped[str] = mapped_column(Text, nullable=False)
    isin: Mapped[str | None] = mapped_column(Text, nullable=True)

    document = relationship("Document", back_populates="funds")
    holdings = relationship("Holding", back_populates="fund")
    transactions = relationship("Transaction", back_populates="fund")


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), nullable=False, index=True)
    opening_units: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    closing_units: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    nav: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    valuation: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    valuation_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)

    fund = relationship("Fund", back_populates="holdings")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), nullable=False, index=True)
    date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    units: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    nav: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    unit_balance: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)

    fund = relationship("Fund", back_populates="transactions")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_amount: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    target_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_funding: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    flexibility: Mapped[str | None] = mapped_column(String(32), nullable=True)
    horizon_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Cashflow(Base):
    __tablename__ = "cashflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    cadence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    monthly_payment: Mapped[object | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Constraint(Base):
    """Reserved for future hard constraints. Not used as a user-facing dashboard."""

    __tablename__ = "constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class UserJourney(Base):
    """Onboarding position and explicit skip/unknown flags for one user."""

    __tablename__ = "user_journeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    current_step: Mapped[str] = mapped_column(String(32), nullable=False, default="welcome")
    finances_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    goals_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    portfolio_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
