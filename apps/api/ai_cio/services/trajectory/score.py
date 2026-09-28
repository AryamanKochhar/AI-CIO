"""Financial trajectory score — deterministic, auditable components."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ai_cio.services.trajectory.math_utils import ZERO, d, money

# Configurable weights (sum need not be 1 — normalized over available components).
DEFAULT_WEIGHTS: dict[str, float] = {
    "savings_rate": 0.18,
    "goal_progress": 0.18,
    "diversification": 0.14,
    "liquidity": 0.14,
    "risk_alignment": 0.12,
    "investment_consistency": 0.14,
    "tax_efficiency": 0.10,
}


def _clamp(score: float | None) -> int | None:
    if score is None:
        return None
    return int(max(0, min(100, round(score))))


def build_trajectory_score(
    *,
    snapshot: dict[str, Any],
    goal_rows: list[dict[str, Any]],
    behavior: dict[str, Any],
    portfolio_health: dict[str, Any] | None = None,
    tax_summary: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    components: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    # Savings rate
    sr = d(snapshot.get("savings_rate_percent"))
    if sr is None:
        components["savings_rate"] = {"score": None, "status": "insufficient_data", "note": "Need income and expenses."}
        missing.append("savings_rate")
    else:
        # 20%+ → ~90, 0% → ~40, negative → lower
        score = 40 + float(sr) * 2.5
        components["savings_rate"] = {
            "score": _clamp(score),
            "status": "ok",
            "note": f"Savings rate ~{sr}% of income (illustrative).",
            "raw": money(sr),
        }

    # Goal progress — average likelihood_percent or coverage
    gp_scores = [g.get("likelihood_percent") for g in goal_rows if g.get("likelihood_percent") is not None]
    if not gp_scores and not goal_rows:
        components["goal_progress"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "No goals on record.",
        }
        missing.append("goal_progress")
    elif not gp_scores:
        components["goal_progress"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Goals exist but funding projection incomplete.",
        }
        missing.append("goal_progress")
    else:
        avg = sum(float(x) for x in gp_scores) / len(gp_scores)
        components["goal_progress"] = {
            "score": _clamp(avg),
            "status": "ok",
            "note": f"Average illustrative goal coverage score across {len(gp_scores)} goal(s).",
        }

    # Diversification from portfolio health if present; else observed concentration discipline
    div = None
    if portfolio_health and isinstance(portfolio_health.get("components"), dict):
        div_comp = portfolio_health["components"].get("diversification") or {}
        if div_comp.get("available") and div_comp.get("score") is not None:
            div = float(div_comp["score"])
    if div is None and isinstance(behavior.get("components"), dict):
        conc = behavior["components"].get("concentration_discipline") or {}
        if conc.get("score") is not None:
            div = float(conc["score"])
            components["diversification"] = {
                "score": _clamp(div),
                "status": "ok",
                "note": "Proxy from observed holding concentration (largest-position share).",
            }
    if div is None and "diversification" not in components:
        components["diversification"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Portfolio diversification score not available.",
        }
        missing.append("diversification")
    elif "diversification" not in components:
        components["diversification"] = {
            "score": _clamp(div),
            "status": "ok",
            "note": "From portfolio health diversification component.",
        }

    # Liquidity — months of expenses
    months = d(snapshot.get("liquid_months_cover"))
    if months is None:
        components["liquidity"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Need liquid savings and expenses for emergency cover.",
        }
        missing.append("liquidity")
    else:
        # 6 months → ~90, 3 → ~70, 1 → ~45
        score = 30 + float(months) * 10
        components["liquidity"] = {
            "score": _clamp(score),
            "status": "ok",
            "note": f"~{months} months of expenses in liquid savings (when known).",
            "raw": money(months),
        }

    # Risk alignment — portfolio health risk, else behaviour score as soft proxy
    risk_score = None
    risk_note = "From portfolio health risk component."
    if portfolio_health and isinstance(portfolio_health.get("components"), dict):
        r = portfolio_health["components"].get("risk") or {}
        if r.get("available") and r.get("score") is not None:
            risk_score = float(r["score"])
    if risk_score is None and behavior.get("behavior_score") is not None:
        risk_score = float(behavior["behavior_score"])
        risk_note = "Proxy from observed investment behavior score (not psychometric risk)."
    if risk_score is None:
        components["risk_alignment"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Risk alignment needs portfolio risk metrics or behaviour context.",
        }
        missing.append("risk_alignment")
    else:
        components["risk_alignment"] = {"score": _clamp(risk_score), "status": "ok", "note": risk_note}

    # Investment consistency from behavior (fall back to trading-frequency discipline)
    cons = behavior.get("components", {}).get("consistency") if isinstance(behavior.get("components"), dict) else None
    if cons is None or cons.get("score") is None:
        freq = (
            behavior.get("components", {}).get("trading_frequency")
            if isinstance(behavior.get("components"), dict)
            else None
        )
        if freq and freq.get("score") is not None:
            components["investment_consistency"] = {
                "score": _clamp(float(freq["score"])),
                "status": "ok",
                "note": freq.get("note") or "Proxy from observed trading frequency.",
            }
        else:
            components["investment_consistency"] = {
                "score": None,
                "status": "insufficient_data",
                "note": "Need transaction history to score contribution consistency.",
            }
            missing.append("investment_consistency")
    else:
        components["investment_consistency"] = {
            "score": _clamp(float(cons["score"])),
            "status": "ok",
            "note": cons.get("note") or "From observed contribution consistency.",
        }

    # Tax efficiency — light heuristic from coverage
    tax_eff = None
    if tax_summary:
        # If analysis available with few missing costs → higher; incomplete → none
        dq = tax_summary.get("data_quality") or {}
        cov = dq.get("coverage_pct")
        if cov is not None:
            tax_eff = min(90, 50 + float(cov) * 0.4)
    if tax_eff is None:
        components["tax_efficiency"] = {
            "score": None,
            "status": "insufficient_data",
            "note": "Tax efficiency needs usable cost-basis coverage from Tax Intelligence.",
        }
        missing.append("tax_efficiency")
    else:
        components["tax_efficiency"] = {
            "score": _clamp(tax_eff),
            "status": "ok",
            "note": "Proxy from tax data-quality coverage (not a tax filing grade).",
        }

    # Weighted overall
    num = 0.0
    den = 0.0
    for key, meta in components.items():
        if meta.get("score") is None:
            continue
        wt = float(w.get(key, 0.1))
        num += meta["score"] * wt
        den += wt
    overall = int(round(num / den)) if den > 0 else None

    supports = [k for k, m in components.items() if m.get("score") is not None and m["score"] >= 75]
    drags = [k for k, m in components.items() if m.get("score") is not None and m["score"] < 55]

    explanations: list[str] = []
    if overall is None:
        explanations.append("Trajectory score unavailable — too many core inputs are missing.")
    else:
        if supports:
            explanations.append(
                "Score is primarily supported by: " + ", ".join(s.replace("_", " ") for s in supports[:3]) + "."
            )
        if drags:
            explanations.append(
                "Score is reduced by: " + ", ".join(s.replace("_", " ") for s in drags[:3]) + "."
            )
        if overall >= 75:
            explanations.append("Your current financial trajectory is broadly aligned with long-term goals under stated assumptions.")
        elif overall >= 55:
            explanations.append("Your trajectory is mixed — some foundations are solid, but goal funding or diversification may need attention.")
        else:
            explanations.append("Your trajectory under current assumptions may leave material goal gaps — review surplus, contributions, and concentration.")

    return {
        "overall_score": overall,
        "max_score": 100,
        "component_scores": components,
        "component_weights": w,
        "explanations": explanations,
        "missing_data": missing,
        "label": (
            "Strong trajectory"
            if overall is not None and overall >= 75
            else "Mixed trajectory"
            if overall is not None and overall >= 55
            else "At-risk trajectory"
            if overall is not None
            else "Insufficient data"
        ),
        "disclaimer": "Not a credit score. Deterministic planning score from available Twin metrics — educational only.",
    }
