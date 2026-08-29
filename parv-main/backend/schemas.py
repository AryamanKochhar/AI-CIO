"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class UserCreate(BaseModel):
    """Schema for creating a user."""
    name: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssessmentSessionCreate(BaseModel):
    """Schema for creating an assessment session."""
    user_id: int


class AssessmentSessionResponse(BaseModel):
    """Schema for assessment session response."""
    id: int
    user_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    status: str

    class Config:
        from_attributes = True


class ResponseCreate(BaseModel):
    """Schema for storing a response."""
    question_id: str
    answer: str
    confidence: int  # 0-100
    response_time_ms: int


class ResponseModel(BaseModel):
    """Schema for response model."""
    id: int
    session_id: int
    question_id: str
    answer: str
    confidence: int
    response_time_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileResponse(BaseModel):
    """Schema for behavioral profile response."""
    id: int
    session_id: int
    user_id: int
    risk_score: float
    loss_aversion_score: float
    anchoring_score: float
    recency_bias_score: float
    herding_score: float
    overconfidence_score: float
    decision_stability_score: float
    average_confidence: float
    average_response_time_ms: float
    profile_confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class AssessmentSummary(BaseModel):
    """Schema for assessment summary (used in history view)."""
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    risk_score: Optional[float]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True
