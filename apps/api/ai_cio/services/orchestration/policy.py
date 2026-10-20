"""Deterministic cross-agent constraints and final evidence checks."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json

from ai_cio.services.cashflow_math import monthly_field
from ai_cio.services.skill_principles import resolve_principle


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def contribution_policy(twin: dict, constraints: dict) -> dict:
    fp = twin.get("financial_position") or {}
    income = monthly_field(fp, "income")
    expenses = monthly_field(fp, "expenses")
    surplus = max(income - expenses, Decimal(0)) if income is not None and expenses is not None else None
    declared = _number(constraints.get("monthly_investment_budget"))
    if declared is not None and declared < 0:
        declared = None
    other = _number(constraints.get("other_goal_monthly_commitments"))
    reserve = _number(constraints.get("reserve_monthly_commitment"))
    earmarks_confirmed = other is not None and reserve is not None and min(other, reserve) >= 0
    ceiling = min(declared, surplus) if declared is not None and surplus is not None else None
    uncommitted = max(ceiling - other - reserve, Decimal(0)) if ceiling is not None and earmarks_confirmed else None
    money = lambda value: f"{value:.2f}" if value is not None else None
    return {"declared_monthly_budget": money(declared), "monthly_surplus": money(surplus), "total_monthly_ceiling": money(ceiling), "other_goal_commitments": money(other), "reserve_commitment": money(reserve), "uncommitted_monthly_ceiling": money(uncommitted), "earmarks_confirmed": earmarks_confirmed, "status": "bounded" if uncommitted is not None else "consent_or_earmarks_required", "scope": "A total shared contribution ceiling, not an additional MF transfer. Existing SIPs, FIRE and other goals must share it. Recorded expenses must already include EMI; do not subtract EMI again.", "psychometric_policy": "Recorded willingness is constrained by financial capacity, goal horizon and access needs. A funding gap or attractive recent return cannot raise the risk limit."}


def validate_review_proof(row: dict) -> dict:
    proof = row.get("proof") or {}
    principles = proof.get("principles") or []
    exact = bool(principles)
    for principle in principles:
        actual = resolve_principle(principle.get("id"))
        exact = exact and bool(actual) and all(principle.get(key) == actual.get(key) for key in ("skill", "section", "excerpt", "skill_sha256"))
    content = {key: value for key, value in proof.items() if key != "digest"}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
    digest_valid = proof.get("digest") == digest
    arithmetic_valid, arithmetic_checked, not_recomputed = True, 0, []
    for calculation in proof.get("calculations") or []:
        operation = calculation.get("operation")
        operands = [_number(value) for value in calculation.get("operands") or []]
        result = _number(calculation.get("result"))
        if operation not in {"difference", "positive_gap", "sum", "ratio", "percent"}:
            not_recomputed.append(calculation.get("label") or operation or "metric")
            continue
        if not operands or any(value is None for value in operands) or result is None:
            arithmetic_valid = False
            continue
        try:
            if operation == "sum":
                expected = sum(operands, Decimal(0))
            elif operation == "difference":
                expected = operands[0] - operands[1]
            elif operation == "positive_gap":
                expected = max(operands[0] - operands[1], Decimal(0))
            else:
                if operands[1] <= 0:
                    raise ValueError("Positive denominator required")
                expected = operands[0] / operands[1] * (100 if operation == "percent" else 1)
            arithmetic_checked += 1
            arithmetic_valid = arithmetic_valid and expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == result
        except (ArithmeticError, ValueError, IndexError):
            arithmetic_valid = False
    return {"finding_id": row.get("id"), "passed": bool(exact and digest_valid and arithmetic_valid), "exact_skill_excerpts": bool(exact), "proof_digest": digest_valid, "arithmetic_checked": arithmetic_checked, "arithmetic_passed": arithmetic_valid, "metrics_not_recomputed_here": not_recomputed, "scope": "Verifies authored proof integrity and supported arithmetic. It does not independently authenticate provider documents or prove financial outcomes."}
