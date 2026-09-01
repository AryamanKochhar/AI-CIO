"""Which analysis steps apply to each kind of decision request."""

from __future__ import annotations

from enum import Enum

from domain.decision.contracts import DecisionObjective


class Capability(str, Enum):
    CAPITAL_ALLOCATION = "capital_allocation"
    GOAL_ALIGNMENT = "goal_alignment"
    RISK_SUITABILITY = "risk_suitability"
    LIQUIDITY_CHECK = "liquidity_check"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    DIVERSIFICATION = "diversification"
    CONCENTRATION = "concentration"


_OBJECTIVE_CAPABILITIES: dict[DecisionObjective, list[Capability]] = {
    DecisionObjective.ALLOCATE_CAPITAL: [
        Capability.CAPITAL_ALLOCATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.LIQUIDITY_CHECK,
    ],
    DecisionObjective.REVIEW_PORTFOLIO: [
        Capability.PORTFOLIO_ANALYSIS,
        Capability.DIVERSIFICATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
    ],
    DecisionObjective.EVALUATE_PORTFOLIO_RISK: [
        Capability.RISK_SUITABILITY,
        Capability.CONCENTRATION,
        Capability.LIQUIDITY_CHECK,
        Capability.DIVERSIFICATION,
    ],
    DecisionObjective.EVALUATE_STRATEGY_SUITABILITY: [
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.LIQUIDITY_CHECK,
    ],
}

_KNOWLEDGE_TOPICS: dict[Capability, list[str]] = {
    Capability.CAPITAL_ALLOCATION: ["allocation", "asset_allocation"],
    Capability.GOAL_ALIGNMENT: ["portfolio"],
    Capability.RISK_SUITABILITY: ["risk", "portfolio"],
    Capability.LIQUIDITY_CHECK: ["portfolio"],
    Capability.PORTFOLIO_ANALYSIS: ["portfolio", "mutual_fund"],
    Capability.DIVERSIFICATION: ["diversification", "concentration"],
    Capability.CONCENTRATION: ["concentration", "diversification"],
}


def capabilities_for_objective(objective: DecisionObjective) -> list[Capability]:
    return list(_OBJECTIVE_CAPABILITIES.get(objective, []))


def knowledge_topics_for(capabilities: list[Capability]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        for topic in _KNOWLEDGE_TOPICS.get(capability, []):
            if topic not in seen:
                seen.add(topic)
                topics.append(topic)
    return topics
