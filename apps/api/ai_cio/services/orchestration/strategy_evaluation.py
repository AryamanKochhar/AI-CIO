"""Score candidate strategies against the user's context."""

from __future__ import annotations

from decimal import Decimal

from domain.decision.contracts import InvestmentContext, InvestmentStrategy, StrategyEvaluation


def evaluate_strategies(
    context: InvestmentContext,
    strategies: list[InvestmentStrategy],
) -> list[StrategyEvaluation]:
    return [_evaluate_one(context, strategy) for strategy in strategies]


def _evaluate_one(context: InvestmentContext, strategy: InvestmentStrategy) -> StrategyEvaluation:
    twin = context.twin
    behaviour = twin.get("behaviour") or {}
    goals = (twin.get("goals") or {}).get("items") or []
    finances = twin.get("financial_position") or {}
    portfolio = twin.get("portfolio") or {}

    willingness = _risk_willingness(behaviour)
    capacity = _risk_capacity(finances, portfolio)
    horizon = _goal_horizon(goals)
    liquidity = _liquidity_fit(finances, strategy)
    concentration = _concentration_note(portfolio)

    conflicts: list[str] = []
    if willingness == "higher" and horizon == "short":
        conflicts.append("Higher risk willingness conflicts with short goal horizon.")
    if capacity == "limited" and strategy.allocation.get("equity", Decimal("0")) > strategy.allocation.get("cash", Decimal("0")):
        conflicts.append("Equity-heavy allocation may exceed financial capacity.")

    strengths: list[str] = []
    weaknesses: list[str] = []
    if liquidity == "good":
        strengths.append("Keeps a usable cash buffer.")
    else:
        weaknesses.append("May leave limited cash for emergencies.")
    if horizon == "long" and strategy.allocation.get("equity", Decimal("0")) > Decimal("0"):
        strengths.append("Includes growth assets for a longer horizon.")
    if concentration:
        weaknesses.append(concentration)

    return StrategyEvaluation(
        strategy=strategy,
        factors={
            "goal_horizon": horizon,
            "liquidity": liquidity,
            "existing_concentration": concentration or "not assessed",
        },
        strengths=strengths,
        weaknesses=weaknesses,
        risks=list(strategy.risks),
        tradeoffs=[
            "More equity may help long-term goals but adds short-term volatility.",
            "More cash improves safety but may reduce growth.",
        ],
        suitability_indicators={
            "risk_willingness": willingness,
            "risk_capacity": capacity,
            "goal_horizon_fit": horizon,
            "liquidity_fit": liquidity,
        },
        conflicts=conflicts,
    )


def _risk_willingness(behaviour: dict) -> str:
    if behaviour.get("status") != "known":
        return "unknown"
    scores = behaviour.get("scores") or {}
    risk = scores.get("risk_score")
    if risk is None:
        return "unknown"
    if risk >= 0.65:
        return "higher"
    if risk <= 0.35:
        return "lower"
    return "moderate"


def _risk_capacity(finances: dict, portfolio: dict) -> str:
    liquid = (finances.get("liquid") or {}).get("known")
    liabilities = (finances.get("liabilities") or {}).get("known")
    has_portfolio = (portfolio.get("total_value") or {}).get("known")
    if liquid and not liabilities:
        return "comfortable"
    if liquid and liabilities:
        return "moderate"
    if has_portfolio:
        return "moderate"
    return "limited"


def _goal_horizon(goals: list[dict]) -> str:
    if not goals:
        return "unknown"
    horizons = [g.get("horizon_years") for g in goals if g.get("horizon_years") is not None]
    if not horizons:
        return "mixed"
    shortest = min(horizons)
    if shortest <= 3:
        return "short"
    if shortest <= 7:
        return "medium"
    return "long"


def _liquidity_fit(finances: dict, strategy: InvestmentStrategy) -> str:
    liquid_known = (finances.get("liquid") or {}).get("known")
    cash_share = strategy.allocation.get("cash", Decimal("0"))
    total = sum(strategy.allocation.values(), Decimal("0"))
    if not liquid_known or total == 0:
        return "unknown"
    if cash_share / total >= Decimal("0.15"):
        return "good"
    return "tight"


def _concentration_note(portfolio: dict) -> str:
    count = portfolio.get("holdings_count") or 0
    if count == 0:
        return ""
    if count <= 3:
        return "Existing portfolio is highly concentrated."
    return ""
