from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FirePlanningInputs(BaseModel):
    """Explicit planning assumptions; default rates are scenarios, not forecasts."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    current_age: int = Field(ge=18, le=99)
    retirement_age: int = Field(default=65, ge=19, le=100)
    monthly_spending_today: float = Field(ge=0, le=1e12)
    monthly_investment_budget: float | None = Field(default=None, ge=0, le=1e12)
    annual_pension_today: float | None = Field(default=None, ge=0, le=1e12)
    earmarked_assets: float = Field(ge=0, le=1e14)
    inflation_percent: float = Field(default=6, ge=0, le=20)
    accumulation_return_percent: float = Field(default=8, ge=-20, le=30)
    withdrawal_rate_percent: float = Field(default=3.5, ge=0.5, le=10)
    longevity_age: int = Field(default=95, ge=20, le=120)
    other_goal_monthly_commitments: float = Field(default=0, ge=0, le=1e12)
    reserve_monthly_commitment: float = Field(default=0, ge=0, le=1e12)
    pension_inflation_linked: bool = False

    @field_validator("current_age", "retirement_age", "longevity_age", mode="before")
    @classmethod
    def whole_ages(cls, value):
        from decimal import Decimal, InvalidOperation
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Age must be a whole number") from exc
        if isinstance(value, bool) or not number.is_finite() or number != number.to_integral_value():
            raise ValueError("Age must be a finite whole number")
        return int(number)

    @field_validator("monthly_spending_today", "monthly_investment_budget", "annual_pension_today",
                     "earmarked_assets", "inflation_percent", "accumulation_return_percent",
                     "withdrawal_rate_percent", "other_goal_monthly_commitments", "reserve_monthly_commitment", mode="before")
    @classmethod
    def non_boolean_numbers(cls, value):
        if isinstance(value, bool):
            raise ValueError("A boolean is not a financial amount or rate")
        return value

    @field_validator("pension_inflation_linked", mode="before")
    @classmethod
    def explicit_boolean(cls, value):
        if not isinstance(value, bool):
            raise ValueError("Pension indexation must be true or false")
        return value

    @model_validator(mode="after")
    def chronological_ages(self):
        if self.retirement_age <= self.current_age:
            raise ValueError("Retirement age must be after current age")
        if self.longevity_age <= self.retirement_age:
            raise ValueError("Longevity age must be after retirement age")
        return self


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
    planning_inputs: FirePlanningInputs | None = None


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
    force_refresh: bool = False


class FixedDepositCreate(BaseModel):
    bank_name: str
    principal: str
    account_label: Optional[str] = None
    interest_rate_pa: Optional[str] = None
    tenure_months: Optional[int] = None
    start_date: Optional[str] = None
    maturity_date: Optional[str] = None
    compounding: Optional[str] = "cumulative"
    is_senior_citizen: bool = False
    notes: Optional[str] = None
