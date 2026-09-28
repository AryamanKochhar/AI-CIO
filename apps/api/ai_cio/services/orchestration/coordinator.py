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
from ai_cio import settings
from ai_cio.services.goal_likelihood import assess_selected_goals, parse_goal_ids
from ai_cio.services.orchestration.adapters import (
    SessionKnowledgeProvider,
    SessionMarketProvider,
    SessionTwinProvider,
)
from ai_cio.services.orchestration.analyzers.simple_allocator import SimpleAllocatorAnalyzer
from ai_cio.services.orchestration.context_builder import build_investment_context
from ai_cio.services.orchestration.errors import DecisionValidationError
from ai_cio.services.orchestration.strategy_evaluation import evaluate_strategies
from ai_cio.services.sector_opportunity import build_sector_opportunity
from ai_cio.services.agents.decision_suggestions import build_decision_suggestions

logger = logging.getLogger(__name__)


def _default_analyzer(objective: DecisionObjective) -> DecisionAnalyzer:
    # Prefer Ling equity agent for equity objective when configured; otherwise
    # detailed rule-based insights cover all objectives.
    if (
        objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO
        and settings.EQUITY_AGENT_ENABLED
        and settings.OPENROUTER_API_KEY
    ):
        from ai_cio.services.agents.equity_agent import EquityAgentAnalyzer

        return EquityAgentAnalyzer()
    return SimpleAllocatorAnalyzer()


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
    decision_analyzer = analyzer or _default_analyzer(request.objective)

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

    stages.append("goal_likelihood")
    goal_ids = parse_goal_ids(request.constraints)
    # Only score goals the user selected; empty selection → empty list.
    goal_likelihood = assess_selected_goals(context.twin, goal_ids) if goal_ids else []

    stages.append("sector_opportunity")
    sector_opportunity: dict[str, Any] = {"available": False, "reason": "disabled", "recommendations": []}
    if settings.SECTOR_OPPORTUNITY_ENABLED:
        try:
            sector_opportunity = build_sector_opportunity(
                context.twin,
                sector_allocation=list(getattr(analysis, "sector_allocation", None) or []),
                true_exposure=dict(getattr(analysis, "true_exposure", None) or {}),
            )
        except Exception as exc:
            logger.warning("sector_opportunity_failed err=%s", exc)
            sector_opportunity = {
                "available": False,
                "reason": str(exc),
                "recommendations": [],
                "sectors": [],
                "deprioritized": [],
            }

    stages.append("suggestions")
    try:
        suggestions = build_decision_suggestions(
            twin=context.twin,
            analysis_bits={
                "portfolio_health": dict(getattr(analysis, "portfolio_health", None) or {}),
                "top_worries": list(getattr(analysis, "top_worries", None) or []),
                "recommended_actions": list(analysis.recommended_actions or []),
            },
            sector_opportunity=sector_opportunity,
            goal_likelihood=goal_likelihood,
        )
    except Exception as exc:
        logger.warning("suggestions_failed err=%s", exc)
        suggestions = {"available": False, "items": [], "reason": str(exc)}

    stages.append("validate")
    decision_text = analysis.decision_summary or _decision_label(request.objective, selected)
    assumptions = list(analysis.assumptions or [])
    if goal_likelihood:
        assumptions.append(
            "Goal likelihood uses an illustrative 10% p.a. nominal return and monthly surplus = income − expenses."
        )
    if sector_opportunity.get("available"):
        assumptions.append(
            "Sector opportunity ranks are rule-based from Dhan index history + Twin exposure — not AI rankings."
        )
    preliminary = DecisionResult(
        decision_id=request.decision_id,
        user_id=request.user_id,
        objective=request.objective,
        decision=decision_text,
        selected_strategy=selected,
        alternatives=alternatives,
        rationale=analysis.observations,
        key_factors=_key_factors(context, evaluations, analysis),
        risks=analysis.risks,
        tradeoffs=analysis.tradeoffs,
        assumptions=assumptions,
        evidence=analysis.evidence,
        strategy_evaluations=evaluations,
        validation=ValidationResult(passed=True),
        confidence=_confidence(context, analysis.missing_information, analysis),
        context_summary=context.to_dict(),
        recommended_actions=list(analysis.recommended_actions or []),
        insight_cards=list(getattr(analysis, "insight_cards", None) or []),
        style_allocation=list(getattr(analysis, "style_allocation", None) or []),
        sector_allocation=list(getattr(analysis, "sector_allocation", None) or []),
        portfolio_health=dict(getattr(analysis, "portfolio_health", None) or {}),
        top_worries=list(getattr(analysis, "top_worries", None) or []),
        concentration_analysis=dict(getattr(analysis, "concentration_analysis", None) or {}),
        true_exposure=dict(getattr(analysis, "true_exposure", None) or {}),
        quality_valuation=dict(getattr(analysis, "quality_valuation", None) or {}),
        goal_likelihood=goal_likelihood,
        sector_opportunity=sector_opportunity,
        suggestions=suggestions,
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
        "agent": getattr(decision_analyzer, "name", type(decision_analyzer).__name__),
        "focus": "equity" if request.objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO else "general",
    }

    logger.info(
        "decision_complete decision_id=%s user_id=%s objective=%s analyzer=%s duration_ms=%s",
        request.decision_id,
        request.user_id,
        request.objective.value,
        type(decision_analyzer).__name__,
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
    if objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO:
        return "Review your equity sleeve for concentration, suitability, and next actions."
    return "Review the decision factors below. This is not a buy or sell instruction."


def _key_factors(context, evaluations, analysis=None) -> list[str]:
    factors = [f"Objective: {context.objective.value}"]
    if analysis is not None:
        for item in getattr(analysis, "recommended_actions", [])[:2]:
            factors.append(f"Action: {item}")
        raw = None
        # Prefer model key_factors if present on strategy characteristics — skip
    if context.missing_optional:
        factors.append(f"Optional gaps: {', '.join(context.missing_optional)}")
    for evaluation in evaluations[:2]:
        for conflict in evaluation.conflicts:
            factors.append(conflict)
    return factors


def _confidence(context, missing: list[str], analysis=None) -> str:
    if analysis is not None and analysis.candidate_strategies:
        hinted = (analysis.candidate_strategies[0].expected_characteristics or {}).get("confidence")
        if hinted in {"low", "medium", "high"}:
            return hinted
    score = sum(1 for value in (context.completeness or {}).values() if value)
    if missing:
        score -= 1
    if score >= 5:
        return "medium"
    if score >= 3:
        return "low"
    return "low"
