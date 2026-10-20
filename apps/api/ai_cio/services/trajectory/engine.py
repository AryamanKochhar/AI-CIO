"""Assemble Financial Trajectory intelligence for Decisions + API."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services.goal_likelihood import parse_goal_ids
from ai_cio.services.trajectory.behavior import analyze_behavior
from ai_cio.services.trajectory.math_utils import ZERO, d, money
from ai_cio.services.trajectory.projection import (
    apply_what_if,
    build_projections,
    project_goals_under_scenarios,
)
from ai_cio.services.trajectory.score import build_trajectory_score
from ai_cio.services.twin import assemble_twin
from ai_cio.services.cashflow_math import monthly_field


def _fp_value(fp: dict[str, Any], key: str) -> Decimal | None:
    node = fp.get(key) or {}
    if isinstance(node, dict):
        return d(node.get("value"))
    return d(node)


def build_financial_snapshot(twin: dict[str, Any]) -> dict[str, Any]:
    fp = twin.get("financial_position") or {}
    pre = (twin.get("preanalysis") or {}).get("financial_health") or {}
    portfolio = twin.get("portfolio") or {}
    income = monthly_field(fp, "income", legacy_monthly=True)
    expenses = monthly_field(fp, "expenses", legacy_monthly=True)
    liquid = _fp_value(fp, "liquid")
    net_worth = _fp_value(fp, "net_worth")
    portfolio_value = d((portfolio.get("total_value") or {}).get("value"))
    fd_node = fp.get("fixed_deposits") or {}
    liab_node = fp.get("liabilities") or {}
    fd_total = d(fd_node.get("total_principal") if isinstance(fd_node, dict) else None)
    liability_total = d(liab_node.get("total_balance") if isinstance(liab_node, dict) else None)

    surplus = None
    savings_rate = None
    if income is not None and expenses is not None:
        surplus = income - expenses
        if income > 0:
            savings_rate = (surplus / income) * Decimal("100")

    # Prefer preanalysis when present
    if fp.get("cashflow_cadence") in (None, "monthly") and income is not None and expenses is not None and pre.get("monthly_surplus") not in (None, ""):
        surplus = d(pre.get("monthly_surplus")) or surplus
    if fp.get("cashflow_cadence") in (None, "monthly") and pre.get("savings_rate_percent") not in (None, ""):
        savings_rate = d(pre.get("savings_rate_percent")) or savings_rate

    liquid_months = None
    if liquid is not None and expenses is not None and expenses > 0:
        liquid_months = liquid / expenses

    investable = (portfolio_value or ZERO) + (fd_total or ZERO)

    return {
        "net_worth": money(net_worth),
        "investable_assets": money(investable if investable > 0 else portfolio_value),
        "monthly_income": money(income),
        "monthly_expenses": money(expenses),
        "monthly_surplus": money(surplus),
        "savings_rate_percent": money(savings_rate),
        "portfolio_value": money(portfolio_value),
        "liquid_savings": money(liquid),
        "fixed_deposits": money(fd_total),
        "liabilities": money(liability_total),
        "liquid_months_cover": money(liquid_months),
        "cadence_assumption": "Annual cashflows divided by 12." if fp.get("cashflow_cadence") == "annual" else "Monthly cashflows as recorded." if fp.get("cashflow_cadence") == "monthly" else "Non-recurring or unknown flows do not establish monthly capacity." if fp.get("cashflow_cadence") else "Legacy snapshot lacks cadence: monthly assumption, requiring confirmation.",
        "known": {
            "income": income is not None,
            "expenses": expenses is not None,
            "liquid": liquid is not None,
            "portfolio": portfolio_value is not None,
        },
    }


def build_trajectory_intelligence(
    twin: dict[str, Any],
    transactions: list[dict[str, Any]],
    *,
    goal_ids: list[int] | None = None,
    horizon_years: int = 20,
    include_liquid_in_principal: bool = False,
    monthly_contribution_override: Decimal | None = None,
    what_if: dict[str, Any] | None = None,
    tax_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = build_financial_snapshot(twin)
    portfolio_value = d(snapshot.get("portfolio_value")) or ZERO
    liquid = d(snapshot.get("liquid_savings")) or ZERO
    principal = portfolio_value + (liquid if include_liquid_in_principal else ZERO)
    surplus = d(snapshot.get("monthly_surplus"))
    monthly = monthly_contribution_override
    if monthly is None:
        monthly = surplus if surplus is not None and surplus > 0 else ZERO

    horizons = sorted(set([5, 10, 15, 20, 25, 30, int(horizon_years)]))
    projections = build_projections(
        principal=principal,
        monthly_contribution=monthly,
        horizons=horizons,
    )

    goal_items = list(((twin.get("goals") or {}).get("items") or []))
    if goal_ids:
        idset = {int(g) for g in goal_ids}
        goal_items = [g for g in goal_items if g.get("id") is not None and int(g["id"]) in idset]

    policy = twin.get("contribution_policy")
    goal_monthly = surplus
    if isinstance(policy, dict):
        goal_monthly = d(policy.get("uncommitted_monthly_ceiling")) if len(goal_items) == 1 else None
    goal_projection = project_goals_under_scenarios(goal_items, monthly_surplus=goal_monthly)

    holdings = (twin.get("portfolio") or {}).get("holdings") or []
    behavior = analyze_behavior(transactions, holdings=holdings)
    portfolio_health = (
        twin.get("portfolio_health")
        or (twin.get("preanalysis") or {}).get("portfolio_health")
        or {}
    )

    score = build_trajectory_score(
        snapshot=snapshot,
        goal_rows=goal_projection,
        behavior=behavior,
        portfolio_health=portfolio_health if isinstance(portfolio_health, dict) else {},
        tax_summary=tax_intelligence,
    )

    insights: list[str] = []
    insights.extend(score.get("explanations") or [])
    for c in (behavior.get("comments") or [])[:3]:
        insights.append(c)
    for g in goal_projection[:3]:
        name = g.get("goal_name") or "Goal"
        status = g.get("likelihood_status")
        if status and status != "unknown":
            insights.append(
                f"{name}: illustrative funding status '{status}' under base (~10% p.a.) assumptions."
            )

    actions: list[str] = []
    if isinstance(policy, dict):
        actions.append("Confirm one shared contribution budget and distinct goal earmarks; projections do not allocate the same surplus to each goal.")
    elif surplus is None:
        actions.append("Add monthly income and expenses so surplus-based projections can run.")
    elif surplus <= 0:
        actions.append("Review expenses vs income — current surplus is zero or negative under recorded figures.")
    else:
        actions.append(
            f"Current illustrative surplus ~₹{money(surplus)}/mo feeds the base projection — consider whether this matches actual SIPs."
        )
    if score.get("overall_score") is not None and score["overall_score"] < 60:
        actions.append("Address score drag factors (liquidity, concentration, or goal gaps) before increasing equity risk.")
    if behavior.get("available") and (behavior.get("behavior_score") or 100) < 55:
        actions.append("Review contribution consistency and concentration — observed behavior may be stressing the trajectory.")
    underfunded = [g for g in goal_projection if g.get("likelihood_status") in {"at_risk", "unlikely"}]
    for g in underfunded[:2]:
        need = g.get("required_monthly_contribution")
        actions.append(
            f"For '{g.get('goal_name')}': review raising contributions toward ~₹{need}/mo (base-scenario estimate)."
            if need
            else f"For '{g.get('goal_name')}': funding looks tight under base assumptions — review target or timeline."
        )

    what_if_result = None
    if what_if:
        what_if_result = apply_what_if(
            principal=principal,
            base_monthly=monthly,
            monthly_override=d(what_if.get("monthly_contribution")),
            return_override=(
                (d(what_if.get("annual_return_percent")) / Decimal("100"))
                if d(what_if.get("annual_return_percent")) is not None
                else None
            ),
            horizon=int(what_if.get("horizon_years") or horizon_years),
            contribution_growth_pa=d(what_if.get("contribution_growth_pa")) or ZERO,
        )

    available = bool(principal > 0 or monthly > 0 or goal_projection or behavior.get("available"))
    return {
        "available": available,
        "status": "success" if available else "insufficient_data",
        "snapshot": snapshot,
        "score": score,
        "projections": projections,
        "goal_projections": goal_projection,
        "behavior": behavior,
        "insights": insights,
        "recommended_actions": actions,
        "what_if": what_if_result,
        "decision_impact": {
            "current_base_15y": ((projections.get("endpoints_by_horizon") or {}).get("15") or {}).get("base"),
            "note": "Use what-if to compare contribution/return changes against this base path.",
        },
        "assumptions": list(projections.get("assumptions") or [])
        + [
            snapshot.get("cadence_assumption"),
            "Each goal scenario uses the contribution budget independently; these paths are not a joint funding allocation.",
            "Psychometric profile is separate from observed transaction behavior.",
        ],
        "disclaimer": (
            "Financial trajectory is an educational planning view with explicit return scenarios — "
            "not a prediction, guarantee, or SEBI-registered advice."
        ),
    }


def run_trajectory_for_user(
    db: Session,
    user_id: int,
    *,
    constraints: dict[str, Any] | None = None,
    tax_intelligence: dict[str, Any] | None = None,
    portfolio_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    twin = db.twin if getattr(db, "decision_snapshot", False) else assemble_twin(db, user_id)
    if portfolio_health:
        twin = {**twin, "portfolio_health": portfolio_health}
    transactions = db.transactions if getattr(db, "decision_snapshot", False) else portfolio_svc.list_transactions(db, user_id)
    constraints = constraints or {}
    goal_ids = parse_goal_ids(constraints)
    horizon = int(constraints.get("projection_horizon_years") or 20)
    include_liquid = bool(constraints.get("include_liquid_in_projection"))
    monthly_override = d(constraints.get("monthly_contribution_override"))
    what_if = constraints.get("what_if") if isinstance(constraints.get("what_if"), dict) else None
    return build_trajectory_intelligence(
        twin,
        transactions,
        goal_ids=goal_ids or None,
        horizon_years=horizon,
        include_liquid_in_principal=include_liquid,
        monthly_contribution_override=monthly_override,
        what_if=what_if,
        tax_intelligence=tax_intelligence,
    )
