"""SQLAlchemy models for the psychometric assessment system."""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.database import Base


class AssessmentStatus(str, enum.Enum):
    """Assessment status enum."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    assessment_sessions = relationship("AssessmentSession", back_populates="user")


class AssessmentSession(Base):
    """Assessment session model."""
    __tablename__ = "assessment_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(AssessmentStatus), default=AssessmentStatus.IN_PROGRESS, nullable=False)

    # Relationships
    user = relationship("User", back_populates="assessment_sessions")
    responses = relationship("Response", back_populates="session", cascade="all, delete-orphan")
    profile = relationship("Profile", back_populates="session", uselist=False, cascade="all, delete-orphan")


class Response(Base):
    """Response model for storing answers to questions."""
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("assessment_sessions.id"), nullable=False)
    question_id = Column(String(10), nullable=False)
    answer = Column(String(100), nullable=False)
    confidence = Column(Integer, nullable=False)  # 0-100
    response_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("AssessmentSession", back_populates="responses")


class Profile(Base):
    """Behavioral profile model."""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("assessment_sessions.id"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Behavioral dimension scores (0-100)
    risk_score = Column(Float, nullable=False)
    loss_aversion_score = Column(Float, nullable=False)
    anchoring_score = Column(Float, nullable=False)
    recency_bias_score = Column(Float, nullable=False)
    herding_score = Column(Float, nullable=False)
    overconfidence_score = Column(Float, nullable=False)
    decision_stability_score = Column(Float, nullable=False)
    
    # Aggregated metrics
    average_confidence = Column(Float, nullable=False)  # 0-100
    average_response_time_ms = Column(Float, nullable=False)
    profile_confidence = Column(Float, nullable=False)  # 0-100
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("AssessmentSession", back_populates="profile")
