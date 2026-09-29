"""Dump Aryaman (user_id=1) decision pipeline I/O for documentation."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from ai_cio.db.session import configure_engine, get_session
from ai_cio.services.twin import assemble_twin
from ai_cio.services.twin_analytics import build_portfolio_preanalysis
from ai_cio.services.agents.equity_agent import _equity_payload
from ai_cio.services.agents.tax_agent import run_tax_agent
from ai_cio.services.agents.fd_agent import run_fd_agent
from ai_cio.services.trajectory import run_trajectory_for_user
from ai_cio.services.behavioral_intelligence import build_behavioral_intelligence
from ai_cio.services.data_quality import build_data_quality_report
from ai_cio.services.decision_trace import (
    build_agent_perspectives,
    build_decision_trace,
    build_temporal_changes,
)
from ai_cio.services.agents.decision_insights import build_detailed_insights


class Enc(json.JSONEncoder):
    def default(self, o):  # noqa: ANN001
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def main() -> None:
    configure_engine()
    db = get_session()
    uid = 1
    twin = assemble_twin(db, uid)
    out_dir = Path("docs")
    out_dir.mkdir(exist_ok=True)

    fp = twin.get("financial_position") or {}
    port = twin.get("portfolio") or {}
    holdings = port.get("holdings") or []
    beh = twin.get("behaviour") or {}
    goals = (twin.get("goals") or {}).get("items") or []

    twin_summary = {
        "user": twin.get("user"),
        "completeness": twin.get("completeness"),
        "behaviour": {
            "status": beh.get("status"),
            "source": beh.get("source"),
            "scores": beh.get("scores"),
            "observations": (beh.get("observations") or [])[:6],
        },
        "financial_position": {
            "income": fp.get("income"),
            "expenses": fp.get("expenses"),
            "liquid": fp.get("liquid"),
            "fixed_deposits": fp.get("fixed_deposits"),
            "liabilities": fp.get("liabilities"),
        },
        "goals": goals,
        "portfolio": {
            "total_value": port.get("total_value"),
            "holding_count": len(holdings),
            "equity_count": len(
                [h for h in holdings if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY"]
            ),
            "top_holdings": [
                {
                    k: h.get(k)
                    for k in (
                        "scheme_name",
                        "isin",
                        "asset_class",
                        "amc",
                        "closing_units",
                        "valuation",
                        "nav",
                    )
                }
                for h in sorted(holdings, key=lambda x: float(x.get("valuation") or 0), reverse=True)[:15]
            ],
            "snapshots": port.get("snapshots") or [],
        },
    }
    (out_dir / "aryaman_twin_summary.json").write_text(
        json.dumps(twin_summary, indent=2, cls=Enc), encoding="utf-8"
    )

    pa = build_portfolio_preanalysis(db, uid)
    eq = _equity_payload(twin, pa)
    detailed = build_detailed_insights(twin=twin, preanalysis=pa, objective="review_equity_portfolio")
    equity_in = {
        "user": eq.get("user"),
        "behaviour": eq.get("behaviour"),
        "goals": eq.get("goals"),
        "financial_position_keys": list((eq.get("financial_position") or {}).keys()),
        "completeness": eq.get("completeness"),
        "equity_sleeve": {
            "counts": eq["equity_sleeve"]["counts"],
            "direct_equity_sample": eq["equity_sleeve"]["direct_equity_holdings"][:8],
            "equity_fund_sample": eq["equity_sleeve"]["equity_oriented_funds"][:8],
        },
        "preanalysis": {
            "portfolio_snapshot": eq["preanalysis"].get("portfolio_snapshot"),
            "concentration": eq["preanalysis"].get("concentration"),
            "portfolio_flags": eq["preanalysis"].get("portfolio_flags"),
            "financial_health": eq["preanalysis"].get("financial_health"),
            "data_gaps": eq["preanalysis"].get("data_gaps"),
            "insight_cards": (eq["preanalysis"].get("insight_cards") or [])[:6],
            "holding_metrics_sample": (eq["preanalysis"].get("holding_metrics") or [])[:8],
        },
        "market_data": eq.get("market_data"),
    }
    (out_dir / "aryaman_equity_agent_input.json").write_text(
        json.dumps(equity_in, indent=2, cls=Enc), encoding="utf-8"
    )

    tax = run_tax_agent(db, uid)
    tax_out = {
        "available": tax.get("available"),
        "agent": tax.get("agent"),
        "rule_version": tax.get("rule_version"),
        "summary": tax.get("summary"),
        "opportunities": (tax.get("opportunities") or [])[:5],
        "comments": (tax.get("comments") or [])[:6],
        "data_quality": tax.get("data_quality"),
        "missing_data_sample": (tax.get("missing_data") or [])[:8],
        "disclaimer": tax.get("disclaimer"),
    }
    (out_dir / "aryaman_tax_output.json").write_text(
        json.dumps(tax_out, indent=2, cls=Enc), encoding="utf-8"
    )

    fd = run_fd_agent(db, uid)
    fd_out = {
        "available": fd.get("available"),
        "summary": fd.get("summary"),
        "comments": fd.get("comments"),
        "opportunities": (fd.get("opportunities") or [])[:5],
    }
    (out_dir / "aryaman_fd_output.json").write_text(
        json.dumps(fd_out, indent=2, cls=Enc), encoding="utf-8"
    )

    traj = run_trajectory_for_user(db, uid, constraints={"goal_ids": [g["id"] for g in goals]})
    traj_out = {
        "available": traj.get("available"),
        "score": traj.get("score"),
        "snapshot": traj.get("snapshot"),
        "behavior": {
            "available": (traj.get("behavior") or {}).get("available"),
            "behavior_score": (traj.get("behavior") or {}).get("behavior_score"),
            "comments": (traj.get("behavior") or {}).get("comments"),
            "components": (traj.get("behavior") or {}).get("components"),
            "metrics": (traj.get("behavior") or {}).get("metrics"),
        },
        "insights": traj.get("insights"),
        "recommended_actions": traj.get("recommended_actions"),
        "projections": {
            "scenarios": (traj.get("projections") or {}).get("scenarios"),
            "horizons": (traj.get("projections") or {}).get("horizons"),
            "endpoints_by_horizon": (traj.get("projections") or {}).get("endpoints_by_horizon"),
            "assumptions": (traj.get("projections") or {}).get("assumptions"),
        },
        "goal_projections": traj.get("goal_projections"),
        "assumptions": traj.get("assumptions"),
        "disclaimer": traj.get("disclaimer"),
    }
    (out_dir / "aryaman_trajectory_output.json").write_text(
        json.dumps(traj_out, indent=2, cls=Enc), encoding="utf-8"
    )

    # Rule-based analysis bits (what LLM would synthesize over)
    analysis_bits = {
        "top_worries": (detailed.get("top_worries") or [])[:6],
        "recommended_actions": (detailed.get("recommended_actions") or [])[:6],
        "observations": (detailed.get("observations") or [])[:8],
        "risks": (detailed.get("risks") or [])[:6],
        "tradeoffs": (detailed.get("tradeoffs") or [])[:4],
        "portfolio_health": detailed.get("portfolio_health"),
        "concentration_analysis": detailed.get("concentration_analysis")
        or (pa.get("concentration") if isinstance(pa, dict) else {}),
        "decision_summary": detailed.get("decision_summary"),
    }
    (out_dir / "aryaman_rule_insights.json").write_text(
        json.dumps(analysis_bits, indent=2, cls=Enc), encoding="utf-8"
    )

    perspectives = build_agent_perspectives(
        analysis_agent="EquityAgentAnalyzer / SimpleAllocatorAnalyzer",
        analysis_focus="equity",
        decision=analysis_bits.get("decision_summary") or "Review equity portfolio",
        top_worries=analysis_bits["top_worries"],
        recommended_actions=analysis_bits["recommended_actions"],
        tax_intelligence=tax,
        fd_intelligence=fd,
        trajectory_intelligence=traj,
        sector_opportunity={"available": False, "reason": "omitted in dump"},
        goal_likelihood=[],
        tradeoffs=analysis_bits["tradeoffs"],
        risks=analysis_bits["risks"],
    )
    trace = build_decision_trace(
        decision=analysis_bits.get("decision_summary") or "Review equity portfolio",
        confidence="medium",
        key_factors=(detailed.get("key_factors") or [])[:8],
        rationale=analysis_bits["observations"],
        assumptions=(detailed.get("assumptions") or [])[:6],
        risks=analysis_bits["risks"],
        tradeoffs=analysis_bits["tradeoffs"],
        recommended_actions=analysis_bits["recommended_actions"],
        top_worries=analysis_bits["top_worries"],
        concentration_analysis=analysis_bits["concentration_analysis"] or {},
        true_exposure=detailed.get("true_exposure") or {},
        tax_intelligence=tax,
        fd_intelligence=fd,
        trajectory_intelligence=traj,
        sector_opportunity={},
        goal_likelihood=[],
        execution={"stages": ["build_context", "analyze", "tax_agent", "fd_agent", "trajectory", "decision_trace"], "analyzer": "dump"},
        twin=twin,
    )
    beh_intel = build_behavioral_intelligence(
        twin=twin,
        observed_behavior=traj.get("behavior"),
        concentration_analysis=analysis_bits["concentration_analysis"] or {},
    )
    dq = build_data_quality_report(
        twin=twin,
        tax_intelligence=tax,
        concentration_analysis=analysis_bits["concentration_analysis"] or {},
        trajectory_intelligence=traj,
    )
    temporal = build_temporal_changes(twin)

    composed = {
        "agent_perspectives": perspectives,
        "decision_trace": trace,
        "behavioral_intelligence": beh_intel,
        "data_quality": dq,
        "temporal_changes": temporal,
    }
    (out_dir / "aryaman_decision_outputs.json").write_text(
        json.dumps(composed, indent=2, cls=Enc), encoding="utf-8"
    )
    print("Wrote docs/aryaman_*.json")
    db.close()


if __name__ == "__main__":
    main()
