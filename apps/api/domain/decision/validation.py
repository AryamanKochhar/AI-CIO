"""Hard checks on a decision result. Pure math and rules — no AI."""

from __future__ import annotations

from decimal import Decimal

from domain.decision.contracts import DecisionObjective, DecisionRequest, DecisionResult, ValidationResult

TOLERANCE = Decimal("0.01")


def validate_decision(request: DecisionRequest, result: DecisionResult) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if request.objective == DecisionObjective.ALLOCATE_CAPITAL:
        _validate_capital_allocation(request, result, errors, warnings)

    if result.selected_strategy is None and request.objective == DecisionObjective.ALLOCATE_CAPITAL:
        errors.append("No strategy was selected for a capital allocation request.")

    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)


def _validate_capital_allocation(
    request: DecisionRequest,
    result: DecisionResult,
    errors: list[str],
    warnings: list[str],
) -> None:
    capital = request.available_capital
    if capital is None:
        errors.append("available_capital is required for allocate_capital.")
        return

    for strategy in [result.selected_strategy, *result.alternatives]:
        if strategy is None:
            continue
        total = sum(strategy.allocation.values(), Decimal("0"))
        if abs(total - capital) > TOLERANCE:
            errors.append(f"Strategy '{strategy.name}' allocation totals {total}, expected {capital}.")
        for bucket, amount in strategy.allocation.items():
            if amount < 0:
                errors.append(f"Strategy '{strategy.name}' has negative {bucket} allocation.")

    min_reserve = request.constraints.get("min_liquid_reserve")
    if min_reserve not in (None, "") and result.selected_strategy is not None:
        reserve = Decimal(str(min_reserve))
        cash = result.selected_strategy.allocation.get("cash", Decimal("0"))
        if cash < reserve:
            warnings.append(
                f"Selected strategy cash ({cash}) is below min_liquid_reserve ({reserve})."
            )
