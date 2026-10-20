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
    TAX_ANALYSIS = "tax_analysis"
    FD_ANALYSIS = "fd_analysis"
    MF_ANALYSIS = "mf_analysis"
    BOND_ANALYSIS = "bond_analysis"


_OBJECTIVE_CAPABILITIES: dict[DecisionObjective, list[Capability]] = {
    DecisionObjective.REVIEW_BOND_PORTFOLIO: [Capability.BOND_ANALYSIS, Capability.GOAL_ALIGNMENT, Capability.RISK_SUITABILITY, Capability.LIQUIDITY_CHECK, Capability.PORTFOLIO_ANALYSIS, Capability.TAX_ANALYSIS, Capability.FD_ANALYSIS],
    DecisionObjective.REVIEW_MUTUAL_FUND_PORTFOLIO: [Capability.MF_ANALYSIS, Capability.PORTFOLIO_ANALYSIS, Capability.GOAL_ALIGNMENT, Capability.RISK_SUITABILITY, Capability.DIVERSIFICATION, Capability.TAX_ANALYSIS, Capability.FD_ANALYSIS],
    DecisionObjective.PLAN_FIRE: [Capability.GOAL_ALIGNMENT, Capability.RISK_SUITABILITY, Capability.LIQUIDITY_CHECK, Capability.FD_ANALYSIS],
    DecisionObjective.ALLOCATE_CAPITAL: [
        Capability.CAPITAL_ALLOCATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.LIQUIDITY_CHECK,
        Capability.FD_ANALYSIS,
    ],
    DecisionObjective.REVIEW_PORTFOLIO: [
        Capability.PORTFOLIO_ANALYSIS,
        Capability.DIVERSIFICATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.TAX_ANALYSIS,
        Capability.FD_ANALYSIS,
    ],
    DecisionObjective.EVALUATE_PORTFOLIO_RISK: [
        Capability.RISK_SUITABILITY,
        Capability.CONCENTRATION,
        Capability.LIQUIDITY_CHECK,
        Capability.DIVERSIFICATION,
        Capability.TAX_ANALYSIS,
        Capability.FD_ANALYSIS,
    ],
    DecisionObjective.EVALUATE_STRATEGY_SUITABILITY: [
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.LIQUIDITY_CHECK,
        Capability.FD_ANALYSIS,
    ],
    DecisionObjective.REVIEW_EQUITY_PORTFOLIO: [
        Capability.PORTFOLIO_ANALYSIS,
        Capability.CONCENTRATION,
        Capability.DIVERSIFICATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.TAX_ANALYSIS,
        Capability.FD_ANALYSIS,
    ],
    DecisionObjective.EXPLORE_COUNTERFACTUALS: [
        Capability.PORTFOLIO_ANALYSIS,
        Capability.CONCENTRATION,
        Capability.DIVERSIFICATION,
        Capability.GOAL_ALIGNMENT,
        Capability.RISK_SUITABILITY,
        Capability.TAX_ANALYSIS,
        Capability.FD_ANALYSIS,
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
    Capability.TAX_ANALYSIS: ["portfolio", "tax"],
    Capability.FD_ANALYSIS: ["portfolio", "debt", "fixed_income"],
    Capability.MF_ANALYSIS: ["mutual_fund", "portfolio", "diversification", "fee_drag"],
    Capability.BOND_ANALYSIS: ["bonds", "fixed_income", "duration", "portfolio", "debt"],
}


def capabilities_for_objective(objective: DecisionObjective) -> list[Capability]:
    values = list(_OBJECTIVE_CAPABILITIES.get(objective, []))
    if objective in {DecisionObjective.REVIEW_PORTFOLIO, DecisionObjective.REVIEW_EQUITY_PORTFOLIO, DecisionObjective.EVALUATE_PORTFOLIO_RISK, DecisionObjective.ALLOCATE_CAPITAL, DecisionObjective.EXPLORE_COUNTERFACTUALS} and Capability.MF_ANALYSIS not in values:
        values.append(Capability.MF_ANALYSIS)
    if Capability.BOND_ANALYSIS not in values:
        values.append(Capability.BOND_ANALYSIS)
    return values


def knowledge_topics_for(capabilities: list[Capability]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        for topic in _KNOWLEDGE_TOPICS.get(capability, []):
            if topic not in seen:
                seen.add(topic)
                topics.append(topic)
    return topics
