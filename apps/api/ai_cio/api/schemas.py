from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    name: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str] = None
    created_at: datetime


class AssessmentSessionCreate(BaseModel):
    user_id: int


class AssessmentSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    instrument_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    status: str


class ResponseCreate(BaseModel):
    question_id: str
    answer: str
    confidence: int = Field(ge=0, le=100)
    response_time_ms: int


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    user_id: int
    instrument_id: int
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
    polarity: dict
    created_at: datetime


class FinancesUpdate(BaseModel):
    income: Optional[str] = None
    expenses: Optional[str] = None
    liquid: Optional[str] = None
    cadence: str = "monthly"
    liabilities: list[dict] = Field(default_factory=list)
    skipped: bool = False


class GoalCreate(BaseModel):
    name: str
    goal_type: str = "other"
    target_amount: Optional[str] = None
    target_date: Optional[str] = None
    current_funding: Optional[str] = None
    priority: str = "medium"
    flexibility: str = "somewhat"
    horizon_years: Optional[int] = None
    notes: Optional[str] = None


class JourneyUpdate(BaseModel):
    current_step: Optional[str] = None
    finances_status: Optional[str] = None
    goals_status: Optional[str] = None
    portfolio_status: Optional[str] = None


class ReviewDecision(BaseModel):
    decision: str
    notes: Optional[str] = None


class AssessmentSummary(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    risk_score: Optional[float]
    created_at: Optional[datetime]


class DecisionRequestBody(BaseModel):
    objective: str
    available_capital: Optional[str] = None
    constraints: dict = Field(default_factory=dict)
    requested_action: Optional[str] = None
