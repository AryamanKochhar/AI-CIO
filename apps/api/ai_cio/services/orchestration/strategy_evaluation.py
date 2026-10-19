"""Score candidate strategies against the user's context."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

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
    # Input presence does not establish financial loss capacity. Do not create a
    # strategy conflict from an unimplemented capacity assessment.

    strengths: list[str] = []
    weaknesses: list[str] = []
    if liquidity == "good":
        strengths.append("Candidate cash share meets the illustrative 15% review policy; emergency-fund adequacy is not assessed.")
    elif liquidity == "tight":
        weaknesses.append("Candidate cash share is below the illustrative 15% review policy; this does not establish an emergency-fund shortfall.")
    else:
        weaknesses.append("Liquidity fit is not assessed because recorded liquidity or the candidate allocation amount is unavailable.")
    if horizon == "long" and strategy.allocation.get("equity", Decimal("0")) > Decimal("0"):
        strengths.append("Includes growth assets for a longer horizon.")
    if concentration:
        weaknesses.append(concentration)

    return StrategyEvaluation(
        strategy=strategy,
        factors={
            "goal_horizon": horizon,
            "liquidity": liquidity,
            "liquidity_basis": "15% candidate cash-share review policy only; no essential-expense coverage calculation",
            "existing_concentration": concentration or "not assessed",
        },
        strengths=strengths,
        weaknesses=weaknesses,
        risks=list(strategy.risks),
        tradeoffs=[
            "More equity may help long-term goals but adds short-term volatility.",
            "A larger candidate cash share may improve near-term flexibility but reduces exposure to growth assets; access terms and inflation still matter.",
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
    risk = _finite_nonnegative(scores.get("risk_score"))
    # Psychometric scoring normalizes canonical risk_score to 0--100. Never
    # guess an alternate scale from a small number (0.65 is a low score).
    if risk is None or risk > Decimal("100"):
        return "unknown"
    if risk >= Decimal("65"):
        return "higher"
    if risk <= Decimal("35"):
        return "lower"
    return "moderate"


def _risk_capacity(finances: dict, portfolio: dict) -> str:
    """Describe coverage only; no financial loss-capacity model exists here.

    A recorded zero is a usable fact, unlike a missing/unusable amount. Neither
    zero liquidity, a portfolio balance nor an unknown liability record alone
    establishes ability to bear loss. Income durability, essential commitments,
    access restrictions and goal funding also need an explicit assessment.
    """
    fields = [
        (finances.get("income"), "value"),
        (finances.get("expenses"), "value"),
        (finances.get("liquid"), "value"),
        (finances.get("liabilities"), "total_balance"),
        (portfolio.get("total_value"), "value"),
    ]
    for field, amount_key in fields:
        if isinstance(field, dict) and field.get("known") is True:
            if _finite_nonnegative(field.get(amount_key)) is not None:
                return "not_fully_assessed"
    return "unknown"


def _finite_nonnegative(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


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
    """Illustrative candidate cash-share policy, not emergency-fund adequacy."""
    liquid = finances.get("liquid") or {}
    liquid_known = liquid.get("known") is True and _finite_nonnegative(liquid.get("value")) is not None
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
        return "Few positions are recorded; underlying exposure and fund look-through require review before assessing concentration."
    return ""
