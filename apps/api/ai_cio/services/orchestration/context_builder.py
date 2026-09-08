"""Build InvestmentContext from a decision request and existing user data."""

from __future__ import annotations

from domain.decision.capabilities import capabilities_for_objective, knowledge_topics_for
from domain.decision.contracts import DecisionObjective, DecisionRequest, InvestmentContext
from domain.decision.ports import KnowledgeProvider, MarketDataProvider, TwinDataProvider
from ai_cio.services.orchestration.errors import InsufficientDecisionContext


def build_investment_context(
    request: DecisionRequest,
    *,
    twin_provider: TwinDataProvider,
    market_provider: MarketDataProvider,
    knowledge_provider: KnowledgeProvider,
) -> InvestmentContext:
    twin = twin_provider.load_twin(request.user_id)
    market_context = market_provider.load_market_context(request.user_id)
    completeness = dict(twin.get("completeness") or {})
    missing_required: list[str] = []
    missing_optional: list[str] = []

    _check_objective_requirements(request, twin, completeness, missing_required, missing_optional)

    capabilities = capabilities_for_objective(request.objective)
    topics = knowledge_topics_for(capabilities)
    knowledge = knowledge_provider.resolve(objective=request.objective, topics=topics)

    if not market_context.get("available"):
        missing_optional.append("market_data")

    if missing_required:
        raise InsufficientDecisionContext(
            f"Missing required information: {', '.join(missing_required)}"
        )

    return InvestmentContext(
        user_id=request.user_id,
        decision_id=request.decision_id,
        objective=request.objective,
        twin=twin,
        market_context=market_context,
        knowledge_evidence=knowledge,
        decision_parameters={
            "available_capital": request.available_capital,
            "constraints": request.constraints,
            "requested_action": request.requested_action,
        },
        completeness=completeness,
        missing_required=missing_required,
        missing_optional=missing_optional,
    )


def _check_objective_requirements(
    request: DecisionRequest,
    twin: dict,
    completeness: dict[str, bool],
    missing_required: list[str],
    missing_optional: list[str],
) -> None:
    if request.objective == DecisionObjective.ALLOCATE_CAPITAL:
        if request.available_capital is None:
            missing_required.append("available_capital")
        if not completeness.get("goals"):
            missing_optional.append("goals")
        if twin.get("behaviour", {}).get("status") != "known":
            missing_optional.append("psychometric_profile")

    if request.objective in {
        DecisionObjective.REVIEW_PORTFOLIO,
        DecisionObjective.EVALUATE_PORTFOLIO_RISK,
        DecisionObjective.REVIEW_EQUITY_PORTFOLIO,
    }:
        if not completeness.get("portfolio"):
            missing_required.append("portfolio")
        if request.objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO:
            if twin.get("behaviour", {}).get("status") != "known":
                missing_optional.append("psychometric_profile")
            if not completeness.get("goals"):
                missing_optional.append("goals")

    if request.objective == DecisionObjective.EVALUATE_STRATEGY_SUITABILITY:
        if not completeness.get("goals"):
            missing_required.append("goals")
