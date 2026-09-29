"""Declared (psychometric) vs observed (transactions/portfolio) behaviour — no diagnosis."""
from __future__ import annotations

from typing import Any


def _risk_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 70:
        return "higher stated comfort with investment risk"
    if score >= 40:
        return "moderate stated risk tolerance"
    return "lower stated risk tolerance"


def build_behavioral_intelligence(
    *,
    twin: dict[str, Any] | None,
    observed_behavior: dict[str, Any] | None,
    concentration_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured DECLARED / OBSERVED / DIVERGENCE from existing Twin + trajectory behavior."""
    twin = twin or {}
    behaviour = twin.get("behaviour") if isinstance(twin.get("behaviour"), dict) else {}
    observed = observed_behavior if isinstance(observed_behavior, dict) else {}
    concentration = concentration_analysis if isinstance(concentration_analysis, dict) else {}

    declared: dict[str, Any] = {
        "available": behaviour.get("status") == "known",
        "source": behaviour.get("source"),
        "items": [],
        "status": behaviour.get("status") or "unknown",
    }
    scores = behaviour.get("scores") if isinstance(behaviour.get("scores"), dict) else {}
    if declared["available"] and scores:
        risk = scores.get("risk_score")
        try:
            risk_f = float(risk) if risk is not None else None
        except (TypeError, ValueError):
            risk_f = None
        band = _risk_band(risk_f)
        if band:
            declared["items"].append(
                {
                    "label": "Risk tolerance (questionnaire)",
                    "value": band,
                    "score": risk_f,
                    "note": "From psychometric assessment — declared preference, not observed trading.",
                }
            )
        for key, label in (
            ("loss_aversion_score", "Loss-aversion tendency (questionnaire)"),
            ("decision_stability_score", "Decision stability (questionnaire)"),
            ("overconfidence_score", "Overconfidence check (questionnaire)"),
        ):
            raw = scores.get(key)
            if raw is None:
                continue
            try:
                declared["items"].append(
                    {
                        "label": label,
                        "value": f"Score {float(raw):.0f}/100",
                        "score": float(raw),
                        "note": "Questionnaire dimension — not a clinical diagnosis.",
                    }
                )
            except (TypeError, ValueError):
                continue
        for obs in (behaviour.get("observations") or [])[:4]:
            if isinstance(obs, str) and obs.strip():
                declared["items"].append(
                    {
                        "label": "Profile observation",
                        "value": obs.strip(),
                        "score": None,
                        "note": "Generated from questionnaire scores.",
                    }
                )
    elif not declared["available"]:
        declared["items"].append(
            {
                "label": "Psychometric profile",
                "value": "Not evaluated",
                "score": None,
                "note": "Complete the behavioural questionnaire to populate declared preferences.",
            }
        )

    observed_block: dict[str, Any] = {
        "available": bool(observed.get("available")),
        "source": observed.get("source") or "observed_transactions",
        "items": [],
        "behavior_score": observed.get("behavior_score"),
        "status": observed.get("status") or "not_evaluated",
    }
    if observed_block["available"]:
        for comment in (observed.get("comments") or [])[:5]:
            observed_block["items"].append(
                {
                    "label": "Observed pattern",
                    "value": comment,
                    "note": "From uploaded transactions / holdings.",
                }
            )
        comps = observed.get("components") if isinstance(observed.get("components"), dict) else {}
        conc = comps.get("concentration_discipline") or {}
        if conc.get("largest_holding_percent") is not None:
            observed_block["items"].append(
                {
                    "label": "Largest holding (observed)",
                    "value": f"{conc.get('largest_holding_percent')}% of valued holdings",
                    "note": conc.get("note"),
                }
            )
        cons = comps.get("consistency") or {}
        if cons.get("note"):
            observed_block["items"].append(
                {
                    "label": "Contribution consistency",
                    "value": cons.get("note"),
                    "note": f"Score {cons.get('score')}" if cons.get("score") is not None else None,
                }
            )
        freq = comps.get("trading_frequency") or {}
        if freq.get("note"):
            observed_block["items"].append(
                {
                    "label": "Trading frequency",
                    "value": freq.get("note"),
                    "note": None,
                }
            )
    else:
        reason = (observed.get("comments") or ["Not evaluated"])[0] if observed else "Not evaluated"
        observed_block["items"].append(
            {
                "label": "Observed investment behaviour",
                "value": reason if observed else "Not evaluated",
                "note": "Needs dated transaction history to evaluate.",
            }
        )

    # Also surface concentration from portfolio analysis when present
    largest = concentration.get("largest_holding_percent")
    if largest is not None and observed_block["available"]:
        try:
            largest_f = float(largest)
            if largest_f >= 20 and not any(
                "largest holding" in str(i.get("value") or "").lower() for i in observed_block["items"]
            ):
                observed_block["items"].append(
                    {
                        "label": "Portfolio concentration",
                        "value": f"Largest holding ~{largest_f:.1f}% (portfolio analysis)",
                        "note": "From concentration_analysis — observable portfolio state.",
                    }
                )
        except (TypeError, ValueError):
            pass

    divergences: list[dict[str, Any]] = []
    risk_score = None
    if declared["available"] and scores.get("risk_score") is not None:
        try:
            risk_score = float(scores["risk_score"])
        except (TypeError, ValueError):
            risk_score = None

    largest_obs = None
    conc_comp = (observed.get("components") or {}).get("concentration_discipline") or {}
    if conc_comp.get("largest_holding_percent") is not None:
        try:
            largest_obs = float(conc_comp["largest_holding_percent"])
        except (TypeError, ValueError):
            largest_obs = None
    if largest_obs is None and largest is not None:
        try:
            largest_obs = float(largest)
        except (TypeError, ValueError):
            largest_obs = None

    if risk_score is not None and largest_obs is not None and risk_score < 55 and largest_obs >= 25:
        divergences.append(
            {
                "title": "Stated risk vs concentration",
                "summary": (
                    f"Your stated risk tolerance is {_risk_band(risk_score)}, while the current portfolio "
                    f"shows a relatively high single-holding concentration (~{largest_obs:.1f}%)."
                ),
                "confidence": "medium",
                "causation_claimed": False,
                "evidence": {
                    "declared_risk_score": risk_score,
                    "largest_holding_percent": largest_obs,
                },
            }
        )

    loss = scores.get("loss_aversion_score") if declared["available"] else None
    sell_ratio = (observed.get("metrics") or {}).get("sell_to_buy_ratio")
    try:
        sell_ratio_f = float(sell_ratio) if sell_ratio is not None else None
    except (TypeError, ValueError):
        sell_ratio_f = None
    try:
        loss_f = float(loss) if loss is not None else None
    except (TypeError, ValueError):
        loss_f = None
    # Higher loss_aversion_score = more adaptive / less bias per polarity docs
    if loss_f is not None and loss_f < 40 and sell_ratio_f is not None and sell_ratio_f > 0.6:
        divergences.append(
            {
                "title": "Questionnaire vs sell activity",
                "summary": (
                    "Questionnaire loss-aversion score is on the lower (more reactive) side, and "
                    "observed sell-like activity is elevated relative to buys. This is an observable "
                    "co-occurrence — not proof of causation."
                ),
                "confidence": "low",
                "causation_claimed": False,
                "evidence": {"loss_aversion_score": loss_f, "sell_to_buy_ratio": sell_ratio_f},
            }
        )

    return {
        "available": declared["available"] or observed_block["available"],
        "declared": declared,
        "observed": observed_block,
        "divergences": divergences,
        "disclaimer": (
            "Describes declared questionnaire answers and observable portfolio/transaction patterns. "
            "Not a psychological diagnosis. Divergence does not prove causation."
        ),
    }
