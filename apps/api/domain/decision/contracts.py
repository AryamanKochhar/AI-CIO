"""Data shapes for investment decisions. No database or AI imports here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4


class DecisionObjective(str, Enum):
    ALLOCATE_CAPITAL = "allocate_capital"
    REVIEW_PORTFOLIO = "review_portfolio"
    EVALUATE_PORTFOLIO_RISK = "evaluate_portfolio_risk"
    EVALUATE_STRATEGY_SUITABILITY = "evaluate_strategy_suitability"
    REVIEW_EQUITY_PORTFOLIO = "review_equity_portfolio"
    REVIEW_MUTUAL_FUND_PORTFOLIO = "review_mutual_fund_portfolio"
    REVIEW_BOND_PORTFOLIO = "review_bond_portfolio"
    EXPLORE_COUNTERFACTUALS = "explore_counterfactuals"
    PLAN_FIRE = "plan_fire"


def _money_dict(allocation: dict[str, Decimal]) -> dict[str, str]:
    return {key: f"{value:.2f}" for key, value in allocation.items()}


@dataclass(frozen=True)
class Evidence:
    source: str
    section: str
    reference: str
    content: str
    relevance: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "section": self.section,
            "reference": self.reference,
            "content": self.content,
            "relevance": self.relevance,
        }


@dataclass(frozen=True)
class DecisionRequest:
    user_id: int
    objective: DecisionObjective
    available_capital: Decimal | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    requested_action: str | None = None
    decision_id: str = field(default_factory=lambda: str(uuid4()))

    @classmethod
    def from_payload(
        cls,
        *,
        user_id: int,
        objective: str,
        available_capital: str | Decimal | None = None,
        constraints: dict[str, Any] | None = None,
        requested_action: str | None = None,
    ) -> DecisionRequest:
        capital = None
        if available_capital not in (None, ""):
            capital = Decimal(str(available_capital))
        try:
            obj = DecisionObjective(objective)
        except ValueError as exc:
            raise ValueError(
                f"Unknown decision objective '{objective}'. "
                "Restart the API if you just added a new option."
            ) from exc
        return cls(
            user_id=user_id,
            objective=obj,
            available_capital=capital,
            constraints=dict(constraints or {}),
            requested_action=requested_action,
        )


@dataclass
class InvestmentContext:
    """Everything needed for one decision. Twin is the main source of user data."""

    user_id: int
    decision_id: str
    objective: DecisionObjective
    twin: dict[str, Any]
    market_context: dict[str, Any]
    knowledge_evidence: list[Evidence]
    decision_parameters: dict[str, Any]
    completeness: dict[str, bool]
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "decision_id": self.decision_id,
            "objective": self.objective.value,
            "completeness": self.completeness,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "built_at": self.built_at.isoformat(),
            "knowledge_count": len(self.knowledge_evidence),
            "market_available": bool(self.market_context.get("available")),
        }


@dataclass
class InvestmentStrategy:
    name: str
    allocation: dict[str, Decimal]
    rationale: list[str]
    assumptions: list[str]
    expected_characteristics: dict[str, str]
    risks: list[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "allocation": _money_dict(self.allocation),
            "rationale": self.rationale,
            "assumptions": self.assumptions,
            "expected_characteristics": self.expected_characteristics,
            "risks": self.risks,
            "constraints": self.constraints,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass
class StrategyEvaluation:
    strategy: InvestmentStrategy
    factors: dict[str, str]
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
    tradeoffs: list[str]
    suitability_indicators: dict[str, str]
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.to_dict(),
            "factors": self.factors,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "risks": self.risks,
            "tradeoffs": self.tradeoffs,
            "suitability_indicators": self.suitability_indicators,
            "conflicts": self.conflicts,
        }


@dataclass
class AnalysisResult:
    observations: list[str]
    candidate_strategies: list[InvestmentStrategy]
    risks: list[str]
    tradeoffs: list[str]
    assumptions: list[str]
    evidence: list[Evidence]
    missing_information: list[str]
    capabilities_used: list[str] = field(default_factory=list)
    decision_summary: str | None = None
    recommended_actions: list[str] = field(default_factory=list)
    insight_cards: list[dict[str, str]] = field(default_factory=list)
    style_allocation: list[dict[str, Any]] = field(default_factory=list)
    sector_allocation: list[dict[str, Any]] = field(default_factory=list)
    portfolio_health: dict[str, Any] = field(default_factory=dict)
    top_worries: list[dict[str, Any]] = field(default_factory=list)
    concentration_analysis: dict[str, Any] = field(default_factory=dict)
    true_exposure: dict[str, Any] = field(default_factory=dict)
    quality_valuation: dict[str, Any] = field(default_factory=dict)
    goal_likelihood: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observations": self.observations,
            "candidate_strategies": [strategy.to_dict() for strategy in self.candidate_strategies],
            "risks": self.risks,
            "tradeoffs": self.tradeoffs,
            "assumptions": self.assumptions,
            "evidence": [item.to_dict() for item in self.evidence],
            "missing_information": self.missing_information,
            "capabilities_used": self.capabilities_used,
            "decision_summary": self.decision_summary,
            "recommended_actions": self.recommended_actions,
            "insight_cards": self.insight_cards,
            "style_allocation": self.style_allocation,
            "sector_allocation": self.sector_allocation,
            "portfolio_health": self.portfolio_health,
            "top_worries": self.top_worries,
            "concentration_analysis": self.concentration_analysis,
            "true_exposure": self.true_exposure,
            "quality_valuation": self.quality_valuation,
            "goal_likelihood": self.goal_likelihood,
        }


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | bool | list[str]]:
        return {"passed": self.passed, "errors": self.errors, "warnings": self.warnings}


@dataclass
class DecisionResult:
    decision_id: str
    user_id: int
    objective: DecisionObjective
    decision: str
    selected_strategy: InvestmentStrategy | None
    alternatives: list[InvestmentStrategy]
    rationale: list[str]
    key_factors: list[str]
    risks: list[str]
    tradeoffs: list[str]
    assumptions: list[str]
    evidence: list[Evidence]
    strategy_evaluations: list[StrategyEvaluation]
    validation: ValidationResult
    confidence: str
    context_summary: dict[str, Any]
    execution: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    insight_cards: list[dict[str, str]] = field(default_factory=list)
    style_allocation: list[dict[str, Any]] = field(default_factory=list)
    sector_allocation: list[dict[str, Any]] = field(default_factory=list)
    portfolio_health: dict[str, Any] = field(default_factory=dict)
    top_worries: list[dict[str, Any]] = field(default_factory=list)
    concentration_analysis: dict[str, Any] = field(default_factory=dict)
    true_exposure: dict[str, Any] = field(default_factory=dict)
    quality_valuation: dict[str, Any] = field(default_factory=dict)
    goal_likelihood: list[dict[str, Any]] = field(default_factory=list)
    sector_opportunity: dict[str, Any] = field(default_factory=dict)
    suggestions: dict[str, Any] = field(default_factory=dict)
    tax_intelligence: dict[str, Any] = field(default_factory=dict)
    fd_intelligence: dict[str, Any] = field(default_factory=dict)
    trajectory_intelligence: dict[str, Any] = field(default_factory=dict)
    decision_trace: dict[str, Any] = field(default_factory=dict)
    agent_perspectives: dict[str, Any] = field(default_factory=dict)
    temporal_changes: dict[str, Any] = field(default_factory=dict)
    behavioral_intelligence: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    counterfactuals: dict[str, Any] = field(default_factory=dict)
    sector_day_changes: dict[str, Any] = field(default_factory=dict)
    holding_market_data: dict[str, Any] = field(default_factory=dict)
    fire_plan: dict[str, Any] = field(default_factory=dict)
    mutual_fund_intelligence: dict[str, Any] = field(default_factory=dict)
    bond_intelligence: dict[str, Any] = field(default_factory=dict)
    orchestration: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "user_id": self.user_id,
            "objective": self.objective.value,
            "decision": self.decision,
            "selected_strategy": self.selected_strategy.to_dict() if self.selected_strategy else None,
            "alternatives": [strategy.to_dict() for strategy in self.alternatives],
            "rationale": self.rationale,
            "key_factors": self.key_factors,
            "risks": self.risks,
            "tradeoffs": self.tradeoffs,
            "assumptions": self.assumptions,
            "evidence": [item.to_dict() for item in self.evidence],
            "strategy_evaluations": [item.to_dict() for item in self.strategy_evaluations],
            "validation": self.validation.to_dict(),
            "confidence": self.confidence,
            "context_summary": self.context_summary,
            "execution": self.execution,
            "recommended_actions": self.recommended_actions,
            "insight_cards": self.insight_cards,
            "style_allocation": self.style_allocation,
            "sector_allocation": self.sector_allocation,
            "portfolio_health": self.portfolio_health,
            "top_worries": self.top_worries,
            "concentration_analysis": self.concentration_analysis,
            "true_exposure": self.true_exposure,
            "quality_valuation": self.quality_valuation,
            "goal_likelihood": self.goal_likelihood,
            "sector_opportunity": self.sector_opportunity,
            "suggestions": self.suggestions,
            "tax_intelligence": self.tax_intelligence,
            "fd_intelligence": self.fd_intelligence,
            "trajectory_intelligence": self.trajectory_intelligence,
            "decision_trace": self.decision_trace,
            "agent_perspectives": self.agent_perspectives,
            "temporal_changes": self.temporal_changes,
            "behavioral_intelligence": self.behavioral_intelligence,
            "data_quality": self.data_quality,
            "counterfactuals": self.counterfactuals,
            "sector_day_changes": self.sector_day_changes,
            "holding_market_data": self.holding_market_data,
            "fire_plan": self.fire_plan,
            "mutual_fund_intelligence": self.mutual_fund_intelligence,
            "bond_intelligence": self.bond_intelligence,
            "orchestration": self.orchestration,
        }
