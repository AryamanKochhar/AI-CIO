"""Run the full decision pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from domain.decision.capabilities import capabilities_for_objective
from domain.decision.contracts import DecisionObjective, DecisionRequest, DecisionResult, ValidationResult
from domain.decision.ports import DecisionAnalyzer
from domain.decision.validation import validate_decision
from ai_cio.services.orchestration.adapters import (
    SessionKnowledgeProvider,
    SessionMarketProvider,
    SessionTwinProvider,
)
from ai_cio.services.orchestration.analyzers.simple_allocator import SimpleAllocatorAnalyzer
from ai_cio.services.orchestration.context_builder import build_investment_context
from ai_cio.services.orchestration.errors import DecisionValidationError
from ai_cio.services.orchestration.strategy_evaluation import evaluate_strategies

logger = logging.getLogger(__name__)


def run_decision(
    db: Session,
    request: DecisionRequest,
    *,
    analyzer: DecisionAnalyzer | None = None,
) -> dict[str, Any]:
    """Entry point used by the API. Returns a plain dict for JSON responses."""
    started = time.perf_counter()
    stages: list[str] = []

    twin_provider = SessionTwinProvider(db)
    market_provider = SessionMarketProvider(db)
    knowledge_provider = SessionKnowledgeProvider()
    decision_analyzer = analyzer or SimpleAllocatorAnalyzer()

    stages.append("build_context")
    context = build_investment_context(
        request,
        twin_provider=twin_provider,
        market_provider=market_provider,
        knowledge_provider=knowledge_provider,
    )

    stages.append("resolve_capabilities")
    capabilities = capabilities_for_objective(request.objective)

    stages.append("analyze")
    analysis = decision_analyzer.analyze(context, capabilities=capabilities)

    stages.append("evaluate_strategies")
    evaluations = evaluate_strategies(context, analysis.candidate_strategies)
    selected, alternatives = _pick_strategy(analysis.candidate_strategies, evaluations)

    stages.append("validate")
    preliminary = DecisionResult(
        decision_id=request.decision_id,
        user_id=request.user_id,
        objective=request.objective,
        decision=_decision_label(request.objective, selected),
        selected_strategy=selected,
        alternatives=alternatives,
        rationale=analysis.observations,
        key_factors=_key_factors(context, evaluations),
        risks=analysis.risks,
        tradeoffs=analysis.tradeoffs,
        assumptions=analysis.assumptions,
        evidence=analysis.evidence,
        strategy_evaluations=evaluations,
        validation=ValidationResult(passed=True),
        confidence=_confidence(context, analysis.missing_information),
        context_summary=context.to_dict(),
    )
    validation = validate_decision(request, preliminary)
    preliminary.validation = validation

    if not validation.passed:
        raise DecisionValidationError("; ".join(validation.errors))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    preliminary.execution = {
        "stages": stages,
        "capabilities": [cap.value for cap in capabilities],
        "duration_ms": elapsed_ms,
        "analyzer": type(decision_analyzer).__name__,
    }

    logger.info(
        "decision_complete decision_id=%s user_id=%s objective=%s duration_ms=%s",
        request.decision_id,
        request.user_id,
        request.objective.value,
        elapsed_ms,
    )

    return preliminary.to_dict()


def _pick_strategy(strategies, evaluations):
    if not strategies:
        return None, []
    if not evaluations:
        return strategies[0], strategies[1:]

    ranked = sorted(
        evaluations,
        key=lambda item: (len(item.conflicts), len(item.weaknesses), -len(item.strengths)),
    )
    best_name = ranked[0].strategy.name
    selected = next(s for s in strategies if s.name == best_name)
    alternatives = [s for s in strategies if s is not selected]
    return selected, alternatives


def _decision_label(objective: DecisionObjective, selected) -> str:
    if objective == DecisionObjective.ALLOCATE_CAPITAL and selected:
        return f"Review a {selected.name.lower()} allocation split for the available capital."
    if objective == DecisionObjective.REVIEW_PORTFOLIO:
        return "Review portfolio fit against goals, concentration, and risk factors."
    if objective == DecisionObjective.EVALUATE_PORTFOLIO_RISK:
        return "Review portfolio risk using willingness, capacity, and holdings together."
    return "Review the decision factors below. This is not a buy or sell instruction."


def _key_factors(context, evaluations) -> list[str]:
    factors = [f"Objective: {context.objective.value}"]
    if context.missing_optional:
        factors.append(f"Optional gaps: {', '.join(context.missing_optional)}")
    for evaluation in evaluations[:2]:
        for conflict in evaluation.conflicts:
            factors.append(conflict)
    return factors


def _confidence(context, missing: list[str]) -> str:
    score = sum(1 for value in (context.completeness or {}).values() if value)
    if missing:
        score -= 1
    if score >= 5:
        return "medium"
    if score >= 3:
        return "low"
    return "low"
