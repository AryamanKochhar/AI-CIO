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
from ai_cio.services.agents.tax_agent import run_tax_agent, tax_impact_for_actions
from ai_cio.services.agents.fd_agent import run_fd_agent, fd_impact_for_actions
from ai_cio.services.trajectory import run_trajectory_for_user
from ai_cio.services.decision_trace import (
    build_agent_perspectives,
    build_decision_trace,
    build_temporal_changes,
)
from ai_cio.services.behavioral_intelligence import build_behavioral_intelligence
from ai_cio.services.data_quality import build_data_quality_report
from ai_cio.services.counterfactuals import build_counterfactuals
from ai_cio.services.counterfactual_ai import enrich_counterfactuals_with_ai

logger = logging.getLogger(__name__)


def _default_analyzer(objective: DecisionObjective) -> DecisionAnalyzer:
    # Prefer equity LLM agent for equity objective when configured; otherwise
    # detailed rule-based insights cover all objectives.
    if (
        objective
        in {
            DecisionObjective.REVIEW_EQUITY_PORTFOLIO,
            DecisionObjective.EXPLORE_COUNTERFACTUALS,
        }
        and settings.EQUITY_AGENT_ENABLED
        and settings.equity_llm_configured()
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
    try:
        analysis = decision_analyzer.analyze(context, capabilities=capabilities)
    except Exception as exc:
        logger.warning("analyzer_failed analyzer=%s err=%s; falling back to SimpleAllocatorAnalyzer", type(decision_analyzer).__name__, exc)
        analysis = SimpleAllocatorAnalyzer().analyze(context, capabilities=capabilities)
        analysis.assumptions = list(analysis.assumptions or []) + [
            f"Primary analyzer failed ({type(decision_analyzer).__name__}); used rule-based fallback."
        ]

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

    stages.append("tax_agent")
    tax_intelligence: dict[str, Any] = {"available": False, "status": "skipped", "comments": []}
    if settings.TAX_INTELLIGENCE_ENABLED:
        try:
            tax_intelligence = run_tax_agent(db, request.user_id)
            tax_intelligence["tax_implications_for_recommendations"] = tax_impact_for_actions(
                tax_intelligence,
                list(analysis.recommended_actions or []),
            )
        except Exception as exc:
            logger.warning("tax_agent_failed err=%s", exc)
            tax_intelligence = {
                "available": False,
                "agent": "tax_agent",
                "status": "error",
                "reason": str(exc),
                "opportunities": [],
                "comments": [],
            }

    stages.append("fd_agent")
    fd_intelligence: dict[str, Any] = {"available": False, "status": "skipped", "comments": []}
    if settings.FD_INTELLIGENCE_ENABLED:
        try:
            fd_intelligence = run_fd_agent(db, request.user_id)
            fd_intelligence["fd_implications_for_recommendations"] = fd_impact_for_actions(
                fd_intelligence,
                list(analysis.recommended_actions or []),
            )
        except Exception as exc:
            logger.warning("fd_agent_failed err=%s", exc)
            fd_intelligence = {
                "available": False,
                "agent": "fd_agent",
                "status": "error",
                "reason": str(exc),
                "opportunities": [],
                "comments": [],
            }

    stages.append("trajectory")
    trajectory_intelligence: dict[str, Any] = {"available": False, "status": "skipped"}
    if settings.TRAJECTORY_INTELLIGENCE_ENABLED:
        try:
            trajectory_intelligence = run_trajectory_for_user(
                db,
                request.user_id,
                constraints=dict(request.constraints or {}),
                tax_intelligence=tax_intelligence if tax_intelligence.get("available") else None,
                portfolio_health=dict(getattr(analysis, "portfolio_health", None) or {}),
            )
        except Exception as exc:
            logger.warning("trajectory_failed err=%s", exc)
            trajectory_intelligence = {
                "available": False,
                "status": "error",
                "reason": str(exc),
                "insights": [],
                "recommended_actions": [],
            }

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
    if tax_intelligence.get("available"):
        assumptions.append(
            f"Tax figures use deterministic rule version "
            f"{tax_intelligence.get('rule_version', 'unknown')} — analytical estimates, not tax advice."
        )
    if fd_intelligence.get("available"):
        assumptions.append(
            "FD market rates are scraped/cached public comparison data — confirm with the bank; not investment advice."
        )
    if trajectory_intelligence.get("available"):
        assumptions.append(
            "Financial trajectory uses illustrative conservative/base/optimistic return scenarios with monthly contributions — not predictions."
        )
        for action in (trajectory_intelligence.get("recommended_actions") or [])[:2]:
            if action and action not in (analysis.recommended_actions or []):
                analysis.recommended_actions = list(analysis.recommended_actions or []) + [action]
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
        tax_intelligence=tax_intelligence,
        fd_intelligence=fd_intelligence,
        trajectory_intelligence=trajectory_intelligence,
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
        "focus": (
            "counterfactuals"
            if request.objective == DecisionObjective.EXPLORE_COUNTERFACTUALS
            else ("equity" if request.objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO else "general")
        ),
    }

    stages.append("decision_trace")
    twin_dict = context.twin if isinstance(context.twin, dict) else {}
    preliminary.agent_perspectives = build_agent_perspectives(
        analysis_agent=preliminary.execution.get("agent"),
        analysis_focus=preliminary.execution.get("focus"),
        decision=preliminary.decision,
        top_worries=list(preliminary.top_worries or []),
        recommended_actions=list(preliminary.recommended_actions or []),
        tax_intelligence=preliminary.tax_intelligence or {},
        fd_intelligence=preliminary.fd_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        sector_opportunity=preliminary.sector_opportunity or {},
        goal_likelihood=list(preliminary.goal_likelihood or []),
        tradeoffs=list(preliminary.tradeoffs or []),
        risks=list(preliminary.risks or []),
    )
    preliminary.decision_trace = build_decision_trace(
        decision=preliminary.decision,
        confidence=preliminary.confidence,
        key_factors=list(preliminary.key_factors or []),
        rationale=list(preliminary.rationale or []),
        assumptions=list(preliminary.assumptions or []),
        risks=list(preliminary.risks or []),
        tradeoffs=list(preliminary.tradeoffs or []),
        recommended_actions=list(preliminary.recommended_actions or []),
        top_worries=list(preliminary.top_worries or []),
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
        true_exposure=dict(preliminary.true_exposure or {}),
        tax_intelligence=preliminary.tax_intelligence or {},
        fd_intelligence=preliminary.fd_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        sector_opportunity=preliminary.sector_opportunity or {},
        goal_likelihood=list(preliminary.goal_likelihood or []),
        execution=preliminary.execution,
        twin=twin_dict,
    )
    # Prefer perspectives already embedded in the trace to keep cards identical
    preliminary.agent_perspectives = {
        **preliminary.agent_perspectives,
        "agents": (preliminary.decision_trace.get("steps") or {}).get("specialist_findings")
        or preliminary.agent_perspectives.get("agents"),
    }
    preliminary.temporal_changes = build_temporal_changes(twin_dict)
    preliminary.behavioral_intelligence = build_behavioral_intelligence(
        twin=twin_dict,
        observed_behavior=(preliminary.trajectory_intelligence or {}).get("behavior"),
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
    )
    preliminary.data_quality = build_data_quality_report(
        twin=twin_dict,
        tax_intelligence=preliminary.tax_intelligence or {},
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
    )
    preliminary.counterfactuals = build_counterfactuals(
        twin=twin_dict,
        tax_intelligence=preliminary.tax_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
    )
    # AI narrates / ranks deterministic scenarios — does not recompute maths.
    if preliminary.counterfactuals.get("available"):
        preliminary.counterfactuals = enrich_counterfactuals_with_ai(
            preliminary.counterfactuals,
            twin=twin_dict,
            decision=preliminary.decision,
            top_worries=list(preliminary.top_worries or []),
            recommended_actions=list(preliminary.recommended_actions or []),
            behavioural=preliminary.behavioral_intelligence or {},
        )

    logger.info(
        "decision_complete decision_id=%s user_id=%s objective=%s analyzer=%s duration_ms=%s "
        "agents=%s disagreements=%s temporal=%s",
        request.decision_id,
        request.user_id,
        request.objective.value,
        type(decision_analyzer).__name__,
        elapsed_ms,
        len((preliminary.agent_perspectives or {}).get("agents") or []),
        len((preliminary.agent_perspectives or {}).get("disagreements") or []),
        bool((preliminary.temporal_changes or {}).get("available")),
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
    if objective == DecisionObjective.EXPLORE_COUNTERFACTUALS:
        return "Compare current path vs alternate what-if paths (trim, contributions, tax harvest, emergency cash)."
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
