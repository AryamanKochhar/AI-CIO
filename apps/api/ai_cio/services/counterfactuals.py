"""Deterministic counterfactual / what-if scenarios for Decisions.

Forward contribution what-ifs + recommendation replay + snapshot path divergence.
LLM is never used for the maths — only structured numbers and labels.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ai_cio.services.trajectory.math_utils import ZERO, d, fv_annuity, fv_lump, money, project_path
from ai_cio.services.trajectory.projection import DEFAULT_SCENARIOS, apply_what_if


def _portfolio_value(twin: dict[str, Any]) -> Decimal:
    port = twin.get("portfolio") if isinstance(twin.get("portfolio"), dict) else {}
    tv = port.get("total_value") if isinstance(port.get("total_value"), dict) else {}
    return d(tv.get("value")) or ZERO


def _liquid(twin: dict[str, Any]) -> Decimal:
    fp = twin.get("financial_position") if isinstance(twin.get("financial_position"), dict) else {}
    liq = fp.get("liquid") if isinstance(fp.get("liquid"), dict) else {}
    return d(liq.get("value")) or ZERO


def _surplus_from_traj(traj: dict[str, Any]) -> Decimal:
    snap = traj.get("snapshot") if isinstance(traj.get("snapshot"), dict) else {}
    return d(snap.get("monthly_surplus")) or ZERO


def _trim_largest_holding_scenario(
    *,
    twin: dict[str, Any],
    concentration: dict[str, Any],
    tax_intelligence: dict[str, Any],
    trim_fraction: Decimal = Decimal("0.20"),
) -> dict[str, Any] | None:
    """HOLD vs TRIM X% of largest holding — concentration + illustrative tax."""
    largest_pct = d(concentration.get("largest_holding_percent"))
    port_val = _portfolio_value(twin)
    if largest_pct is None or port_val <= 0:
        return None

    largest_value = port_val * (largest_pct / Decimal("100"))
    trim_value = (largest_value * trim_fraction).quantize(Decimal("0.01"))
    new_largest_value = largest_value - trim_value
    new_port = port_val  # cash stays in portfolio as liquid sleeve for this illustration
    new_largest_pct = (new_largest_value / new_port * Decimal("100")) if new_port > 0 else ZERO

    # Match tax opportunity / unrealized lot on largest-ish loss name if present
    tax_impact = None
    security = None
    opps = list(tax_intelligence.get("opportunities") or []) if tax_intelligence.get("available") else []
    unrealized_lots = []
    lots = (tax_intelligence.get("tax_lots") or {}) if isinstance(tax_intelligence.get("tax_lots"), dict) else {}
    unrealized_lots = list(lots.get("unrealized") or [])

    # Prefer TLH opp amount proportional to trim if same ballpark as largest holding
    if opps:
        top = opps[0]
        security = top.get("security")
        loss = abs(d(top.get("amount")) or ZERO)
        # Illustrative: realize trim_fraction of that position's unrealized P/L if loss, else gain
        realized_pl = -(loss * trim_fraction) if loss > 0 else ZERO
        # Rough CG tax: use summary STCG rate proxy from estimated_tax/stcg if available
        summary = tax_intelligence.get("summary") or {}
        stcg = d(summary.get("stcg")) or ZERO
        est = d(summary.get("estimated_tax")) or ZERO
        rate = (est / stcg) if stcg > 0 else Decimal("0.20")
        if realized_pl < 0:
            tax_impact = money(ZERO)  # realizing loss → no incremental tax; may offset
            tax_note = (
                f"Illustrative: trimming may realize ~{money(abs(realized_pl))} of unrealized loss "
                f"on {security or 'top TLH candidate'} (could offset gains). Not tax advice."
            )
        else:
            tax_impact = money((realized_pl * rate).quantize(Decimal("0.01")))
            tax_note = "Illustrative tax on realizing gains — rule-based estimate only."
    else:
        tax_note = "No usable tax-lot opportunity matched — tax impact shown as unknown."
        tax_impact = None

    hold_path = {
        "label": "HOLD",
        "largest_holding_percent": money(largest_pct),
        "portfolio_value": money(port_val),
        "cash_freed": money(ZERO),
        "illustrative_tax_impact": money(ZERO),
        "summary": "Keep current concentration; no realization event.",
    }
    trim_path = {
        "label": f"TRIM {int(trim_fraction * 100)}% of largest holding",
        "largest_holding_percent": money(new_largest_pct),
        "portfolio_value": money(port_val),
        "cash_freed": money(trim_value),
        "illustrative_tax_impact": tax_impact,
        "security_hint": security,
        "summary": (
            f"Reduce largest weight from {money(largest_pct)}% toward {money(new_largest_pct)}% "
            f"by freeing ~₹{money(trim_value)} (held as cash in this illustration)."
        ),
        "tax_note": tax_note,
    }

    return {
        "id": "trim_vs_hold_largest",
        "kind": "recommendation_replay",
        "title": "What if you trim the largest holding vs hold?",
        "question": (
            f"Largest holding is ~{money(largest_pct)}% of portfolio. "
            f"Compare HOLD vs trimming {int(trim_fraction * 100)}% of that position."
        ),
        "actual": hold_path,
        "alternatives": [trim_path],
        "deltas": {
            "largest_holding_percent_change": money(new_largest_pct - largest_pct),
            "cash_freed": money(trim_value),
            "illustrative_tax_impact": tax_impact,
        },
        "assumptions": [
            "Trim size is illustrative (default 20% of largest holding value).",
            "Proceeds stay as cash inside the Twin for this comparison — not reinvested.",
            "Tax impact uses available lot/opportunity data when present; otherwise unknown.",
            "Not a trade instruction or tax advice.",
        ],
        "confidence": "medium" if tax_impact is not None else "low",
    }


def _contribution_scenarios(
    *,
    twin: dict[str, Any],
    traj: dict[str, Any],
    deltas: list[Decimal] | None = None,
    horizon: int = 15,
) -> dict[str, Any] | None:
    principal = _portfolio_value(twin) + _liquid(twin)
    base_monthly = _surplus_from_traj(traj)
    if principal <= 0 and base_monthly <= 0:
        return None
    deltas = deltas or [Decimal("-5000"), Decimal("5000"), Decimal("10000")]
    alts = []
    base = apply_what_if(
        principal=principal,
        base_monthly=base_monthly,
        monthly_override=base_monthly,
        horizon=horizon,
    )
    for delta in deltas:
        monthly = max(ZERO, base_monthly + delta)
        row = apply_what_if(
            principal=principal,
            base_monthly=base_monthly,
            monthly_override=monthly,
            horizon=horizon,
        )
        alts.append(
            {
                "label": f"Monthly contribution {money(monthly)} (Δ {money(delta)})",
                "monthly_contribution": row.get("monthly_contribution"),
                "projected_value": row.get("projected_value"),
                "base_projected_value": row.get("base_projected_value"),
                "delta_vs_base": row.get("delta_vs_base"),
                "horizon_years": horizon,
            }
        )
    return {
        "id": "contribution_forward",
        "kind": "forward_what_if",
        "title": "What if you change monthly investing by ₹5k / ₹10k?",
        "question": "Forward path under current portfolio+liquid as principal and current surplus as base SIP.",
        "actual": {
            "label": "CURRENT PATH",
            "monthly_contribution": base.get("monthly_contribution"),
            "projected_value": base.get("projected_value"),
            "horizon_years": horizon,
            "assumed_return_percent": "10.00",
        },
        "alternatives": alts,
        "assumptions": [
            "Principal = portfolio value + liquid savings.",
            "Base monthly = Twin income − expenses surplus when known.",
            f"Horizon {horizon}y · base return 10% p.a. illustrative.",
            "Not a prediction or guarantee.",
        ],
        "confidence": "medium",
    }


def _return_assumption_scenarios(
    *,
    twin: dict[str, Any],
    traj: dict[str, Any],
    horizon: int = 15,
) -> dict[str, Any] | None:
    principal = _portfolio_value(twin) + _liquid(twin)
    monthly = _surplus_from_traj(traj)
    if principal <= 0 and monthly <= 0:
        return None
    alts = []
    for name, rate in DEFAULT_SCENARIOS.items():
        row = apply_what_if(
            principal=principal,
            base_monthly=monthly,
            monthly_override=monthly,
            return_override=rate,
            horizon=horizon,
        )
        alts.append(
            {
                "label": f"{name.title()} ({money(rate * 100)}% p.a.)",
                "annual_return_percent": money(rate * 100),
                "projected_value": row.get("projected_value"),
                "horizon_years": horizon,
            }
        )
    base_rate = DEFAULT_SCENARIOS["base"]
    base_fv = apply_what_if(
        principal=principal,
        base_monthly=monthly,
        horizon=horizon,
    )
    return {
        "id": "return_assumptions",
        "kind": "forward_what_if",
        "title": "What if assumed returns are conservative / base / optimistic?",
        "question": "Same contributions; only the return assumption changes.",
        "actual": {
            "label": "BASE (10% p.a.)",
            "projected_value": base_fv.get("projected_value"),
            "annual_return_percent": money(base_rate * 100),
        },
        "alternatives": alts,
        "assumptions": [
            "Uses fixed scenario rates: 6% / 10% / 14% p.a.",
            "Illustrative educational paths — not forecasts.",
        ],
        "confidence": "medium",
    }


def _snapshot_path_divergence(twin: dict[str, Any]) -> dict[str, Any] | None:
    """Actual snapshot path vs alternate if contributions had been steadier / higher."""
    port = twin.get("portfolio") if isinstance(twin.get("portfolio"), dict) else {}
    snaps = [s for s in (port.get("snapshots") or []) if isinstance(s, dict) and s.get("valuation")]
    if len(snaps) < 2:
        return None

    def _key(s: dict[str, Any]) -> str:
        return str(s.get("month_year") or "")

    ordered = sorted(snaps, key=_key)
    actual = [
        {"period": s.get("month_year"), "value": s.get("valuation"), "source": "twin.snapshot"}
        for s in ordered
    ]
    start = d(ordered[0].get("valuation")) or ZERO
    end = d(ordered[-1].get("valuation")) or ZERO
    n = max(1, len(ordered) - 1)
    # Alternate: start + constant monthly add such that we end ~10% above actual end (illustrative policy)
    # Better: alternate = start grown at 10% p.a. over the span with extra ₹5k/mo
    years = Decimal(str(n)) / Decimal("12")
    alt_end = fv_lump(start, DEFAULT_SCENARIOS["base"], float(years)) + fv_annuity(
        Decimal("5000"), DEFAULT_SCENARIOS["base"], float(years)
    )
    # Build simple year-step path along months linearly for display points
    alt_path = []
    for i, s in enumerate(ordered):
        t = Decimal(str(i)) / Decimal(str(max(1, n)))
        # interpolate start → alt_end under the alt policy for display only
        val = start + (alt_end - start) * t
        alt_path.append(
            {
                "period": s.get("month_year"),
                "value": money(val),
                "source": "counterfactual_model",
            }
        )

    return {
        "id": "snapshot_path_divergence",
        "kind": "retrospective_path",
        "title": "What if contributions had been ₹5,000/mo higher along your statement history?",
        "question": (
            "Compare your actual month-end valuations to an illustrative path that starts at the "
            "same first snapshot and adds ₹5k/mo at 10% p.a."
        ),
        "actual": {
            "label": "ACTUAL (statement snapshots)",
            "start_value": ordered[0].get("valuation"),
            "end_value": ordered[-1].get("valuation"),
            "path": actual,
            "change": money(end - start),
        },
        "alternatives": [
            {
                "label": "ALTERNATE (+₹5k/mo @ 10% p.a. from first snapshot)",
                "start_value": money(start),
                "end_value": money(alt_end),
                "path": alt_path,
                "change": money(alt_end - start),
                "delta_vs_actual_end": money(alt_end - end),
            }
        ],
        "assumptions": [
            "Actual path uses Twin portfolio snapshots only — never fabricated history.",
            "Alternate path is a deterministic model from the first snapshot, not security-level replay.",
            "Does not claim you could have earned exactly this return.",
        ],
        "confidence": "low",
    }


def _emergency_cash_scenario(
    *,
    twin: dict[str, Any],
    traj: dict[str, Any],
) -> dict[str, Any] | None:
    liquid = _liquid(twin)
    expenses = d(((traj.get("snapshot") or {}).get("monthly_expenses"))) or ZERO
    port = _portfolio_value(twin)
    if expenses <= 0 or port <= 0:
        return None
    current_months = (liquid / expenses) if expenses > 0 else ZERO
    target_months = Decimal("6")
    need = max(ZERO, (target_months * expenses) - liquid)
    if need <= 0:
        return {
            "id": "emergency_cash",
            "kind": "recommendation_replay",
            "title": "What if you prioritise emergency cash?",
            "question": "Liquid cover vs a 6-month expense buffer.",
            "actual": {
                "label": "CURRENT",
                "liquid": money(liquid),
                "months_cover": money(current_months),
            },
            "alternatives": [
                {
                    "label": "ALREADY AT TARGET",
                    "summary": f"Liquid ~{money(current_months)} months of expenses — at/above 6-month illustration.",
                }
            ],
            "assumptions": ["Target = 6× monthly expenses (illustrative)."],
            "confidence": "medium",
        }

    new_liquid = liquid + need
    new_port = max(ZERO, port - need)
    return {
        "id": "emergency_cash",
        "kind": "recommendation_replay",
        "title": "What if you move equity into a 6-month emergency buffer?",
        "question": f"Need ~₹{money(need)} more liquid to reach 6× expenses.",
        "actual": {
            "label": "CURRENT",
            "liquid": money(liquid),
            "portfolio_value": money(port),
            "months_cover": money(current_months),
        },
        "alternatives": [
            {
                "label": "RAISE CASH (sell ~buffer gap from portfolio)",
                "liquid": money(new_liquid),
                "portfolio_value": money(new_port),
                "months_cover": money(target_months),
                "amount_shifted": money(need),
                "summary": (
                    f"Shift ~₹{money(need)} from portfolio to liquid → ~6 months cover; "
                    f"portfolio residual ~₹{money(new_port)}."
                ),
            }
        ],
        "deltas": {
            "liquid_change": money(need),
            "portfolio_change": money(-need),
        },
        "assumptions": [
            "Assumes you can free the gap from portfolio at current valuation (no price path).",
            "Tax/friction on sale not fully modelled here — see Tax section.",
            "Illustrative liquidity policy — not advice.",
        ],
        "confidence": "medium",
    }


def _tlh_vs_hold(tax_intelligence: dict[str, Any]) -> dict[str, Any] | None:
    if not tax_intelligence.get("available"):
        return None
    opps = list(tax_intelligence.get("opportunities") or [])
    tlh = [o for o in opps if (o.get("type") or "").startswith("tax_loss")]
    if not tlh:
        return None
    top = tlh[0]
    return {
        "id": "tlh_vs_hold",
        "kind": "recommendation_replay",
        "title": "What if you harvest the top tax-loss candidate vs hold?",
        "question": f"Top TLH candidate: {top.get('security') or 'position'}.",
        "actual": {
            "label": "HOLD",
            "summary": "No realization — unrealized loss stays on books; no harvest this year.",
            "illustrative_tax_impact": money(ZERO),
        },
        "alternatives": [
            {
                "label": "HARVEST (illustrative)",
                "security": top.get("security"),
                "isin": top.get("isin"),
                "unrealized_loss": top.get("amount"),
                "estimated_tax_impact": top.get("estimated_tax_impact"),
                "summary": top.get("reason") or top.get("label"),
                "risks": top.get("risks") or [],
            }
        ],
        "assumptions": [
            "Uses Tax Intelligence opportunity row — educational estimate only.",
            "Wash-sale / re-entry / allocation side-effects not fully modelled.",
            "Not tax advice.",
        ],
        "confidence": str(top.get("confidence") or "low"),
    }


def build_counterfactuals(
    *,
    twin: dict[str, Any] | None,
    tax_intelligence: dict[str, Any] | None = None,
    trajectory_intelligence: dict[str, Any] | None = None,
    concentration_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    twin = twin or {}
    tax = tax_intelligence if isinstance(tax_intelligence, dict) else {}
    traj = trajectory_intelligence if isinstance(trajectory_intelligence, dict) else {}
    conc = concentration_analysis if isinstance(concentration_analysis, dict) else {}

    scenarios: list[dict[str, Any]] = []
    for builder in (
        lambda: _trim_largest_holding_scenario(twin=twin, concentration=conc, tax_intelligence=tax),
        lambda: _tlh_vs_hold(tax),
        lambda: _emergency_cash_scenario(twin=twin, traj=traj),
        lambda: _contribution_scenarios(twin=twin, traj=traj),
        lambda: _return_assumption_scenarios(twin=twin, traj=traj),
        lambda: _snapshot_path_divergence(twin),
    ):
        try:
            item = builder()
        except Exception:
            item = None
        if item:
            scenarios.append(item)

    return {
        "available": bool(scenarios),
        "scenarios": scenarios,
        "disclaimer": (
            "Counterfactuals compare an ACTUAL path (observed Twin/tax data) to ALTERNATE paths "
            "from deterministic rules. They are illustrative educational tools — not predictions, "
            "guarantees, or advice to buy/sell."
        ),
    }
