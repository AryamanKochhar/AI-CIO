"""Investment decision domain — pure types and rules, no database or HTTP."""

from domain.decision.capabilities import Capability, capabilities_for_objective, knowledge_topics_for
from domain.decision.contracts import (
    AnalysisResult,
    DecisionObjective,
    DecisionRequest,
    DecisionResult,
    Evidence,
    InvestmentContext,
    InvestmentStrategy,
    StrategyEvaluation,
    ValidationResult,
)
from domain.decision.validation import validate_decision

__all__ = [
    "AnalysisResult",
    "Capability",
    "DecisionObjective",
    "DecisionRequest",
    "DecisionResult",
    "Evidence",
    "InvestmentContext",
    "InvestmentStrategy",
    "StrategyEvaluation",
    "ValidationResult",
    "capabilities_for_objective",
    "knowledge_topics_for",
    "validate_decision",
]
