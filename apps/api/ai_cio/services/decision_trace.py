"""Build an explainable Decision Trace from existing structured decision outputs.

Does NOT expose private LLM chain-of-thought. Only observable pipeline steps,
specialist payloads, and deterministic conflicts already present in the result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_agent_perspectives(
    *,
    analysis_agent: str | None,
    analysis_focus: str | None,
    decision: str,
    top_worries: list[dict[str, Any]],
    recommended_actions: list[str],
    tax_intelligence: dict[str, Any],
    fd_intelligence: dict[str, Any],
    trajectory_intelligence: dict[str, Any],
    sector_opportunity: dict[str, Any],
    goal_likelihood: list[dict[str, Any]],
    tradeoffs: list[str],
    risks: list[str],
) -> dict[str, Any]:
    """Map existing specialist outputs into comparable agent cards."""
    agents: list[dict[str, Any]] = []

    # Portfolio / Equity analyzer (primary)
    portfolio_finding = (top_worries[0]["title"] if top_worries else None) or decision
    portfolio_detail = (top_worries[0].get("detail") if top_worries else None) or (
        recommended_actions[0] if recommended_actions else "Not evaluated"
    )
    agents.append(
        {
            "agent": "portfolio_agent",
            "label": "Portfolio / Equity",
            "status": "available",
            "finding": portfolio_finding,
            "recommendation": recommended_actions[0] if recommended_actions else "Not evaluated",
            "confidence": "medium" if top_worries or recommended_actions else "low",
            "supporting_data": {
                "analyzer": analysis_agent,
                "focus": analysis_focus,
                "worry_count": len(top_worries),
                "action_count": len(recommended_actions),
            },
            "risks": risks[:3],
            "alternatives": [],
            "conflicts_with": [],
            "priority": "high" if top_worries else "information",
            "detail": portfolio_detail,
        }
    )

    # Tax
    tax_available = bool(tax_intelligence.get("available"))
    tax_opps = list(tax_intelligence.get("opportunities") or [])
    tax_comments = list(tax_intelligence.get("comments") or [])
    tax_impl = list(tax_intelligence.get("tax_implications_for_recommendations") or [])
    if tax_intelligence.get("status") == "skipped" or tax_intelligence.get("status") == "disabled":
        tax_status = "not_evaluated"
    elif tax_available:
        tax_status = "available"
    else:
        tax_status = "unavailable"
    agents.append(
        {
            "agent": "tax_agent",
            "label": "Tax",
            "status": tax_status,
            "finding": (
                (tax_opps[0].get("label") or tax_opps[0].get("type") if tax_opps else None)
                or (tax_comments[0] if tax_comments else None)
                or ("Tax analysis incomplete" if tax_status == "unavailable" else "Not evaluated")
            ),
            "recommendation": (
                "Review tax-lot implications before realizing gains/losses"
                if tax_impl or tax_opps
                else "Not evaluated"
            ),
            "confidence": "medium" if tax_available else "low",
            "supporting_data": {
                "stcg": (tax_intelligence.get("summary") or {}).get("stcg"),
                "ltcg": (tax_intelligence.get("summary") or {}).get("ltcg"),
                "estimated_tax": (tax_intelligence.get("summary") or {}).get("estimated_tax"),
                "opportunity_count": len(tax_opps),
            },
            "risks": list((tax_opps[0].get("risks") if tax_opps else None) or [])[:3],
            "alternatives": [],
            "conflicts_with": ["portfolio_agent"] if tax_opps and recommended_actions else [],
            "priority": "opportunity" if tax_opps else "information",
            "detail": (tax_opps[0].get("reason") if tax_opps else None)
            or (tax_impl[0].get("detail") if tax_impl else None)
            or "Not evaluated",
        }
    )

    # FD / Liquidity
    fd_available = bool(fd_intelligence.get("available"))
    fd_status = (
        "not_evaluated"
        if fd_intelligence.get("status") in {"skipped", "disabled"}
        else ("available" if fd_available else "unavailable")
    )
    fd_comments = list(fd_intelligence.get("comments") or [])
    agents.append(
        {
            "agent": "fd_agent",
            "label": "Fixed deposits / cash",
            "status": fd_status,
            "finding": fd_comments[0] if fd_comments else ("FD summary available" if fd_available else "Not evaluated"),
            "recommendation": "Not evaluated",
            "confidence": "medium" if fd_available else "low",
            "supporting_data": dict(fd_intelligence.get("summary") or {}),
            "risks": [],
            "alternatives": [],
            "conflicts_with": [],
            "priority": "information",
            "detail": fd_comments[1] if len(fd_comments) > 1 else (fd_comments[0] if fd_comments else "Not evaluated"),
        }
    )

    # Goals / Trajectory
    traj_available = bool(trajectory_intelligence.get("available"))
    traj_status = (
        "not_evaluated"
        if trajectory_intelligence.get("status") in {"skipped", "disabled"}
        else ("available" if traj_available else "unavailable")
    )
    score = trajectory_intelligence.get("score") or {}
    goal_rows = goal_likelihood or trajectory_intelligence.get("goal_projections") or []
    agents.append(
        {
            "agent": "goal_agent",
            "label": "Goals / Trajectory",
            "status": traj_status if traj_status != "unavailable" or goal_rows else (
                "available" if goal_rows else traj_status
            ),
            "finding": (
                score.get("label")
                or (goal_rows[0].get("narrative") if goal_rows else None)
                or ("Trajectory score available" if traj_available else "Not evaluated")
            ),
            "recommendation": (
                (trajectory_intelligence.get("recommended_actions") or [None])[0]
                or "Not evaluated"
            ),
            "confidence": "medium" if traj_available or goal_rows else "low",
            "supporting_data": {
                "overall_score": score.get("overall_score"),
                "goal_count": len(goal_rows),
            },
            "risks": [],
            "alternatives": [],
            "conflicts_with": [],
            "priority": "watch" if (score.get("overall_score") is not None and score.get("overall_score") < 50) else "information",
            "detail": (score.get("explanations") or [None])[0]
            or (goal_rows[0].get("narrative") if goal_rows else None)
            or "Not evaluated",
        }
    )

    # Sector rules (deterministic, not LLM)
    sector_available = bool(sector_opportunity.get("available"))
    sector_recs = list(sector_opportunity.get("recommendations") or [])
    agents.append(
        {
            "agent": "sector_rules",
            "label": "Sector opportunity (rules)",
            "status": "available" if sector_available else (
                "unavailable" if sector_opportunity.get("reason") else "not_evaluated"
            ),
            "finding": (
                f"Top sector for review: {sector_recs[0].get('name')}"
                if sector_recs
                else (sector_opportunity.get("reason") or "Not evaluated")
            ),
            "recommendation": (
                f"Review {sector_recs[0].get('name')} as a diversification theme"
                if sector_recs
                else "Not evaluated"
            ),
            "confidence": "medium" if sector_available else "low",
            "supporting_data": {
                "recommendation_count": len(sector_recs),
                "benchmark": sector_opportunity.get("benchmark"),
            },
            "risks": [],
            "alternatives": [r.get("name") for r in sector_recs[1:3] if r.get("name")],
            "conflicts_with": [],
            "priority": "opportunity" if sector_recs else "information",
            "detail": (sector_recs[0].get("logic") if sector_recs else None) or "Not evaluated",
        }
    )

    # Detect disagreements from existing tradeoffs + tax caution vs reduce actions
    disagreements: list[dict[str, Any]] = []
    sellish = any(
        any(k in (a or "").lower() for k in ("trim", "reduce", "rebalance", "sell", "cut"))
        for a in recommended_actions
    )
    tax_caution = bool(tax_opps) or any(
        "tax" in str(x.get("label") or "").lower() or "caution" in str(x.get("label") or "").lower()
        for x in tax_impl
    )
    if sellish and tax_caution:
        disagreements.append(
            {
                "title": "Risk reduction vs tax realization",
                "agents": ["portfolio_agent", "tax_agent"],
                "summary": (
                    "Portfolio actions lean toward reducing concentration, while tax intelligence "
                    "flags potential taxable consequences of realizing gains/losses."
                ),
                "portfolio_stance": "REDUCE / REVIEW",
                "tax_stance": "HOLD / REVIEW TAX LOTS",
                "evidence": {
                    "recommended_action": recommended_actions[0] if recommended_actions else None,
                    "tax_opportunity": (tax_opps[0].get("label") if tax_opps else None),
                },
            }
        )
        # Annotate conflicts_with on the cards
        for a in agents:
            if a["agent"] == "portfolio_agent" and "tax_agent" not in a["conflicts_with"]:
                a["conflicts_with"].append("tax_agent")
            if a["agent"] == "tax_agent" and "portfolio_agent" not in a["conflicts_with"]:
                a["conflicts_with"].append("portfolio_agent")

    for t in tradeoffs[:2]:
        disagreements.append(
            {
                "title": "Documented trade-off",
                "agents": ["portfolio_agent", "goal_agent"],
                "summary": t,
                "portfolio_stance": "REVIEW",
                "tax_stance": "Not evaluated",
                "evidence": {"tradeoff": t},
            }
        )

    synthesis = {
        "conclusion": decision,
        "agreement": "mixed" if disagreements else "aligned",
        "primary_conflict": disagreements[0]["summary"] if disagreements else None,
        "note": (
            "CIO synthesis uses existing specialist outputs and documented trade-offs. "
            "It does not expose private model chain-of-thought."
        ),
    }

    return {
        "available": True,
        "agents": agents,
        "disagreements": disagreements,
        "key_disagreement": disagreements[0] if disagreements else None,
        "cio_synthesis": synthesis,
    }


def build_temporal_changes(twin: dict[str, Any] | None) -> dict[str, Any]:
    """Derive 'What changed?' only from existing Twin snapshot history."""
    twin = twin or {}
    portfolio = twin.get("portfolio") if isinstance(twin.get("portfolio"), dict) else {}
    snapshots = list(portfolio.get("snapshots") or [])
    # Expect chronological or any order — sort by month_year string if possible
    def _key(s: dict[str, Any]) -> str:
        return str(s.get("month_year") or "")

    ordered = sorted([s for s in snapshots if isinstance(s, dict)], key=_key)
    items: list[dict[str, Any]] = []
    if len(ordered) >= 2:
        first, last = ordered[0], ordered[-1]
        items.append(
            {
                "metric": "Portfolio valuation",
                "previous_value": first.get("valuation"),
                "current_value": last.get("valuation"),
                "change_amount": last.get("change_amount"),
                "change_pct": last.get("change_pct"),
                "period_from": first.get("month_year"),
                "period_to": last.get("month_year"),
                "contributing_factors": [
                    "Derived from statement month-end snapshots already on the Twin."
                ],
                "confidence": "medium",
            }
        )
        # Intermediate month-over-month if last has change fields
        if last.get("change_pct") is not None or last.get("change_amount") is not None:
            prev = ordered[-2]
            items.append(
                {
                    "metric": "Latest month change",
                    "previous_value": prev.get("valuation"),
                    "current_value": last.get("valuation"),
                    "change_amount": last.get("change_amount"),
                    "change_pct": last.get("change_pct"),
                    "period_from": prev.get("month_year"),
                    "period_to": last.get("month_year"),
                    "contributing_factors": [
                        "Latest snapshot delta from uploaded statements — not a market forecast."
                    ],
                    "confidence": "medium",
                }
            )

    return {
        "available": bool(items),
        "items": items,
        "reason": None if items else "Insufficient historical Twin snapshots to describe changes.",
    }


def build_decision_trace(
    *,
    decision: str,
    confidence: str,
    key_factors: list[str],
    rationale: list[str],
    assumptions: list[str],
    risks: list[str],
    tradeoffs: list[str],
    recommended_actions: list[str],
    top_worries: list[dict[str, Any]],
    concentration_analysis: dict[str, Any],
    true_exposure: dict[str, Any],
    tax_intelligence: dict[str, Any],
    fd_intelligence: dict[str, Any],
    trajectory_intelligence: dict[str, Any],
    sector_opportunity: dict[str, Any],
    goal_likelihood: list[dict[str, Any]],
    execution: dict[str, Any],
    twin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble INPUTS → OBSERVATIONS → CALCULATIONS → AGENTS → CONFLICTS → SYNTHESIS."""
    twin = twin or {}
    fp = twin.get("financial_position") if isinstance(twin.get("financial_position"), dict) else {}
    port = twin.get("portfolio") if isinstance(twin.get("portfolio"), dict) else {}

    inputs: list[dict[str, Any]] = []
    total_value = port.get("total_value") if isinstance(port.get("total_value"), dict) else {}
    if total_value.get("known") and total_value.get("value") is not None:
        inputs.append({"label": "Portfolio value", "value": total_value.get("value"), "source": "twin.portfolio"})
    liquid = fp.get("liquid") if isinstance(fp.get("liquid"), dict) else {}
    if liquid.get("known") and liquid.get("value") is not None:
        inputs.append({"label": "Liquid savings", "value": liquid.get("value"), "source": "twin.financial_position"})

    sectors = list((true_exposure or {}).get("sector_exposure") or [])
    if sectors:
        try:
            ranked = sorted(
                [s for s in sectors if s.get("percent") is not None],
                key=lambda r: float(r.get("percent") or 0),
                reverse=True,
            )
            if ranked:
                top = ranked[0]
                inputs.append(
                    {
                        "label": f"Sector exposure · {top.get('sector')}",
                        "value": f"{top.get('percent')}%",
                        "source": "true_exposure",
                    }
                )
        except (TypeError, ValueError):
            pass

    if concentration_analysis.get("largest_holding_percent") is not None:
        inputs.append(
            {
                "label": "Largest holding",
                "value": f"{concentration_analysis.get('largest_holding_percent')}%",
                "source": "concentration_analysis",
            }
        )

    tax_summary = tax_intelligence.get("summary") or {}
    if tax_intelligence.get("available"):
        if tax_summary.get("estimated_tax") is not None:
            inputs.append(
                {
                    "label": "Estimated CG tax (FY)",
                    "value": tax_summary.get("estimated_tax"),
                    "source": "tax_intelligence",
                }
            )

    observations = []
    for w in top_worries[:5]:
        observations.append(
            {
                "title": w.get("title"),
                "detail": w.get("detail"),
                "severity": w.get("severity"),
                "metric": w.get("metric"),
                "source": "top_worries",
            }
        )
    for line in rationale[:5]:
        if not any(line == o.get("detail") for o in observations):
            observations.append({"title": "Observation", "detail": line, "source": "rationale"})

    calculations = []
    for factor in key_factors[:8]:
        calculations.append({"rule": factor, "source": "key_factors"})
    for a in assumptions[:6]:
        calculations.append({"rule": a, "source": "assumptions"})
    if trajectory_intelligence.get("available"):
        score = trajectory_intelligence.get("score") or {}
        calculations.append(
            {
                "rule": f"Trajectory score {score.get('overall_score')}/{score.get('max_score', 100)} — {score.get('label')}",
                "source": "trajectory_intelligence",
            }
        )
    if sector_opportunity.get("available"):
        calculations.append(
            {
                "rule": "Sector ranks are deterministic from Dhan history + Twin exposure (not LLM picks).",
                "source": "sector_opportunity",
            }
        )

    perspectives = build_agent_perspectives(
        analysis_agent=(execution or {}).get("agent"),
        analysis_focus=(execution or {}).get("focus"),
        decision=decision,
        top_worries=top_worries,
        recommended_actions=recommended_actions,
        tax_intelligence=tax_intelligence,
        fd_intelligence=fd_intelligence,
        trajectory_intelligence=trajectory_intelligence,
        sector_opportunity=sector_opportunity,
        goal_likelihood=goal_likelihood,
        tradeoffs=tradeoffs,
        risks=risks,
    )

    conflicts = list(perspectives.get("disagreements") or [])
    for t in tradeoffs[:3]:
        if not any(t == c.get("summary") for c in conflicts):
            conflicts.append(
                {
                    "title": "Trade-off",
                    "agents": ["cio_synthesis"],
                    "summary": t,
                    "evidence": {"tradeoff": t},
                }
            )

    return {
        "available": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "confidence": confidence,
        "data_freshness": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "stages": list((execution or {}).get("stages") or []),
            "duration_ms": (execution or {}).get("duration_ms"),
            "analyzer": (execution or {}).get("analyzer"),
        },
        "steps": {
            "inputs": inputs,
            "observations": observations,
            "calculations": calculations,
            "specialist_findings": perspectives.get("agents") or [],
            "conflicts": conflicts,
            "cio_synthesis": perspectives.get("cio_synthesis")
            or {"conclusion": decision, "agreement": "aligned"},
            "final_finding": {
                "decision": decision,
                "recommended_actions": recommended_actions[:5],
                "confidence": confidence,
            },
        },
        "disclaimer": (
            "Decision Trace shows the observable pipeline (inputs → rules → specialist outputs → "
            "trade-offs → synthesis). It does not reveal private model chain-of-thought."
        ),
    }
