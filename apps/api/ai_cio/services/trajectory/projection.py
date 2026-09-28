"""Wealth projection + goal funding + sensitivity + what-if."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ai_cio.services.goal_likelihood import assess_goal
from ai_cio.services.trajectory.math_utils import (
    ZERO,
    d,
    fv_annuity,
    fv_lump,
    money,
    project_path,
)

DEFAULT_SCENARIOS = {
    "conservative": Decimal("0.06"),
    "base": Decimal("0.10"),
    "optimistic": Decimal("0.14"),
}

DEFAULT_INFLATION = Decimal("0.06")
DEFAULT_HORIZONS = [5, 10, 15, 20, 25, 30]


def build_projections(
    *,
    principal: Decimal,
    monthly_contribution: Decimal,
    horizons: list[int] | None = None,
    scenarios: dict[str, Decimal] | None = None,
    contribution_growth_pa: Decimal = ZERO,
    inflation: Decimal = DEFAULT_INFLATION,
) -> dict[str, Any]:
    horizons = horizons or list(DEFAULT_HORIZONS)
    scenarios = scenarios or dict(DEFAULT_SCENARIOS)
    max_h = max(horizons)

    series: dict[str, list[dict[str, Any]]] = {}
    endpoints: dict[str, dict[str, Any]] = {}
    for name, rate in scenarios.items():
        path = project_path(
            principal=principal,
            monthly_pmt=monthly_contribution,
            annual_rate=rate,
            years=max_h,
            contribution_growth_pa=contribution_growth_pa,
        )
        series[name] = path
        for h in horizons:
            pt = next((p for p in path if p["year"] == h), None)
            endpoints.setdefault(str(h), {})[name] = pt

    # Sensitivity matrix: contribution × return at base horizon 15
    sense_horizon = 15 if 15 in horizons else max_h
    contrib_levels = [
        monthly_contribution,
        monthly_contribution + Decimal("5000"),
        monthly_contribution + Decimal("10000"),
        monthly_contribution + Decimal("20000"),
    ]
    # Deduplicate and drop negatives
    seen: set[str] = set()
    levels: list[Decimal] = []
    for c in contrib_levels:
        if c < 0:
            continue
        key = money(c) or "0"
        if key not in seen:
            seen.add(key)
            levels.append(c)

    matrix: list[dict[str, Any]] = []
    for c in levels:
        row: dict[str, Any] = {"monthly_contribution": money(c)}
        for name, rate in scenarios.items():
            fv = fv_lump(principal, rate, sense_horizon) + fv_annuity(c, rate, sense_horizon)
            row[name] = money(fv)
        matrix.append(row)

    return {
        "principal": money(principal),
        "monthly_contribution": money(monthly_contribution),
        "contribution_growth_pa": money(contribution_growth_pa * 100),
        "inflation_pa": money(inflation * 100),
        "horizons": horizons,
        "scenarios": {k: money(v * 100) for k, v in scenarios.items()},
        "series": series,
        "endpoints_by_horizon": endpoints,
        "sensitivity_matrix": {
            "horizon_years": sense_horizon,
            "rows": matrix,
        },
        "assumptions": [
            f"Starting principal ₹{money(principal)} (portfolio + optional liquid if included).",
            f"Monthly contribution ₹{money(monthly_contribution)} (from surplus unless overridden).",
            "Monthly compounding with end-of-month contributions.",
            "Scenarios are illustrative assumed returns — not predictions or guarantees.",
            f"Inflation assumption {money(inflation * 100)}% p.a. (shown for context; nominal paths above).",
        ],
        "disclaimer": "Illustrative projections only. Markets, taxes, and contributions will differ.",
    }


def project_goals_under_scenarios(
    goals: list[dict[str, Any]],
    *,
    monthly_surplus: Decimal | None,
    scenarios: dict[str, Decimal] | None = None,
) -> list[dict[str, Any]]:
    scenarios = scenarios or dict(DEFAULT_SCENARIOS)
    out: list[dict[str, Any]] = []
    for g in goals:
        base = assess_goal(g, monthly_surplus=monthly_surplus, annual_return=scenarios["base"])
        scenario_funding: dict[str, Any] = {}
        for name, rate in scenarios.items():
            row = assess_goal(g, monthly_surplus=monthly_surplus, annual_return=rate)
            target = d(row.get("target_amount"))
            projected = d(row.get("projected_corpus"))
            shortfall = None
            if target is not None and projected is not None:
                shortfall = money(target - projected)
            scenario_funding[name] = {
                "projected_corpus": row.get("projected_corpus"),
                "coverage_ratio": row.get("coverage_ratio"),
                "likelihood_status": row.get("likelihood_status"),
                "likelihood_percent": row.get("likelihood_percent"),
                "required_monthly_contribution": row.get("required_monthly_contribution"),
                "shortfall_or_surplus": shortfall,
            }
        out.append(
            {
                **base,
                "scenario_funding": scenario_funding,
                "chart_marker": {
                    "year": base.get("years_remaining"),
                    "target_amount": base.get("target_amount"),
                    "label": base.get("goal_name"),
                },
            }
        )
    return out


def apply_what_if(
    *,
    principal: Decimal,
    base_monthly: Decimal,
    monthly_override: Decimal | None = None,
    return_override: Decimal | None = None,
    horizon: int = 15,
    contribution_growth_pa: Decimal = ZERO,
) -> dict[str, Any]:
    monthly = monthly_override if monthly_override is not None else base_monthly
    rate = return_override if return_override is not None else DEFAULT_SCENARIOS["base"]
    base_fv = fv_lump(principal, DEFAULT_SCENARIOS["base"], horizon) + fv_annuity(
        base_monthly, DEFAULT_SCENARIOS["base"], horizon
    )
    path = project_path(
        principal=principal,
        monthly_pmt=monthly,
        annual_rate=rate,
        years=horizon,
        contribution_growth_pa=contribution_growth_pa,
    )
    alt_fv = d(path[-1]["value"]) or ZERO
    delta = alt_fv - base_fv
    return {
        "horizon_years": horizon,
        "monthly_contribution": money(monthly),
        "annual_return_percent": money(rate * 100),
        "projected_value": money(alt_fv),
        "base_projected_value": money(base_fv),
        "delta_vs_base": money(delta),
        "path": path,
        "note": "What-if vs base scenario (10% p.a., current surplus). Illustrative only.",
    }
