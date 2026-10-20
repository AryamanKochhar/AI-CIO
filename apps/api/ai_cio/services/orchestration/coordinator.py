"""Run the full decision pipeline."""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from domain.decision.capabilities import capabilities_for_objective
from domain.decision.contracts import DecisionObjective, DecisionRequest, DecisionResult, ValidationResult
from domain.decision.ports import DecisionAnalyzer
from domain.decision.validation import validate_decision
from ai_cio import settings
from ai_cio.services.goal_likelihood import assess_selected_goals, parse_goal_ids
from ai_cio.services.orchestration.adapters import (
    SessionKnowledgeProvider,
    SessionMarketProvider,
    SessionTwinProvider,
)
from ai_cio.services.orchestration.analyzers.simple_allocator import SimpleAllocatorAnalyzer
from ai_cio.services.orchestration.context_builder import build_investment_context
from ai_cio.services.orchestration.errors import DecisionValidationError
from ai_cio.services.orchestration.strategy_evaluation import evaluate_strategies
from ai_cio.services.sector_opportunity import build_sector_opportunity
from ai_cio.services.holding_market_data import build_holding_market_data
from ai_cio.services.agents.decision_suggestions import build_decision_suggestions
from ai_cio.services.agents.tax_agent import run_tax_agent, tax_impact_for_actions
from ai_cio.services.agents.fd_agent import run_fd_agent, fd_impact_for_actions
from ai_cio.services.trajectory import run_trajectory_for_user
from ai_cio.services.decision_trace import (
    build_agent_perspectives,
    build_decision_trace,
    build_temporal_changes,
)
from ai_cio.services.behavioral_intelligence import build_behavioral_intelligence
from ai_cio.services.data_quality import build_data_quality_report
from ai_cio.services.counterfactuals import build_counterfactuals
from ai_cio.services.counterfactual_ai import enrich_counterfactuals_with_ai
from ai_cio.services.trendlyne_sectors import fetch_sector_day_changes

from ai_cio.services.orchestration.runtime import OrchestrationRun
from ai_cio.services.orchestration.snapshot import DecisionSnapshot
from ai_cio.services.orchestration.policy import contribution_policy, validate_review_proof
from ai_cio.services.orchestration.narrative import explain_validated_findings
from ai_cio.services.agents.mutual_fund_agent import run_mutual_fund_agent
from ai_cio.services import portfolio as portfolio_svc
from ai_cio.services.mutual_funds_action_checks import evaluate_mutual_fund_action_checks
from ai_cio.services.mutual_funds.integration import reconcile_portfolio_analysis

logger = logging.getLogger(__name__)


def _default_analyzer(objective: DecisionObjective) -> DecisionAnalyzer:
    # Prefer equity LLM agent for equity objective when configured; otherwise
    # detailed rule-based insights cover all objectives.
    if (
        objective
        in {
            DecisionObjective.REVIEW_EQUITY_PORTFOLIO,
            DecisionObjective.EXPLORE_COUNTERFACTUALS,
        }
        and settings.EQUITY_AGENT_ENABLED
        and settings.equity_llm_configured()
    ):
        from ai_cio.services.agents.equity_agent import EquityAgentAnalyzer

        return EquityAgentAnalyzer()
    return SimpleAllocatorAnalyzer()


def run_decision(
    db: Session,
    request: DecisionRequest,
    *,
    analyzer: DecisionAnalyzer | None = None,
) -> dict[str, Any]:
    """Entry point used by the API. Returns a plain dict for JSON responses."""
    if request.objective == DecisionObjective.PLAN_FIRE:
        from ai_cio.services.fire_decision import run_fire_decision
        return run_fire_decision(db, request)

    started = time.perf_counter()
    stages: list[str] = []
    audit = OrchestrationRun(request.decision_id, request.objective.value)
    decision_analyzer = analyzer or _default_analyzer(request.objective)

    stages.append("build_context")
    with audit.stage("build_context", "Read one financial snapshot and formulate the work", details={"objective": request.objective.value, "database_policy": "Read on the request thread; no database sessions enter workers"}):
        context = build_investment_context(
            request, twin_provider=SessionTwinProvider(db),
            market_provider=SessionMarketProvider(db), knowledge_provider=SessionKnowledgeProvider(),
        )
        context.twin = deepcopy(context.twin)
        transactions = portfolio_svc.list_transactions(db, request.user_id) if hasattr(db, "query") else []
        context.twin.setdefault("portfolio", {})["transactions"] = deepcopy(transactions)
        context.twin["portfolio"]["transactions_complete"] = False
        context.twin["portfolio"]["transaction_coverage_note"] = "Transactions visible in the selected statement; complete inception cashflow history has not been independently established."
        context.twin["decision_constraints"] = dict(request.constraints or {})
        capabilities = capabilities_for_objective(request.objective)
        policy = contribution_policy(context.twin, request.constraints or {})
        context.twin["contribution_policy"] = policy
        snapshot = DecisionSnapshot(twin=deepcopy(context.twin), holdings=deepcopy((context.twin.get("portfolio") or {}).get("holdings") or []), transactions=deepcopy(transactions), fixed_deposits=deepcopy(((context.twin.get("financial_position") or {}).get("fixed_deposits") or {}).get("items") or []))

    def equity_worker():
        local = deepcopy(context)
        market = {"available": False, "reason": "Market data disabled", "holdings": []}
        if settings.SECTOR_OPPORTUNITY_ENABLED:
            try:
                market = build_holding_market_data(local.twin)
            except Exception as exc:
                logger.warning("holding_market_data_failed type=%s", type(exc).__name__)
                market = {"available": False, "reason": "Holding market evidence unavailable; no values invented", "holdings": []}
        local.market_context["holding_indicators"] = market
        if market.get("available"):
            local.market_context["available"] = True
        try:
            analysis = decision_analyzer.analyze(local, capabilities=capabilities)
        except Exception as exc:
            logger.warning("analyzer_failed type=%s", type(exc).__name__)
            analysis = SimpleAllocatorAnalyzer().analyze(local, capabilities=capabilities)
            analysis.assumptions = list(analysis.assumptions or []) + ["Primary analyzer unavailable; deterministic portfolio fallback used."]
        return {"available": True, "analysis": analysis, "holding_market_data": market, "status": "success"}

    def goal_worker():
        if not settings.TRAJECTORY_INTELLIGENCE_ENABLED:
            return {"available": False, "status": "disabled"}
        local_constraints = dict(request.constraints or {})
        # A capacity figure is not consent. Joint earmarks must be confirmed before
        # the trajectory presents a new monthly transfer as an agreed plan.
        local_constraints["monthly_contribution_override"] = policy.get("uncommitted_monthly_ceiling") or "0"
        payload = run_trajectory_for_user(deepcopy(snapshot), request.user_id, constraints=local_constraints)
        payload["contribution_policy"] = policy
        payload["assumptions"] = list(payload.get("assumptions") or []) + ["New contributions are zero until total willingness and goal/reserve earmarks are confirmed; positive surplus alone is not consent."]
        return payload

    tasks = {
        "equity_agent": {"label": "Equity and portfolio specialist", "run": equity_worker, "execution_mode": "llm_with_deterministic_fallback" if type(decision_analyzer).__name__ == "EquityAgentAnalyzer" else "deterministic"},
        "mutual_fund_agent": {"label": "Mutual fund specialist", "run": lambda: run_mutual_fund_agent(deepcopy(context.twin)) if settings.MUTUAL_FUND_AGENT_ENABLED else {"available": False, "status": "disabled"}},
        "tax_agent": {"label": "Tax specialist", "run": lambda: run_tax_agent(deepcopy(snapshot), request.user_id)},
        "fd_agent": {"label": "Fixed deposit specialist", "run": lambda: run_fd_agent(deepcopy(snapshot), request.user_id)},
        "trajectory_agent": {"label": "Goals and trajectory specialist", "run": goal_worker},
    }
    stages.extend(["resolve_capabilities", "parallel_specialists", "analyze", "tax_agent", "fd_agent", "trajectory", "mutual_fund_agent"])
    with audit.stage("parallel_specialists", "Run independent specialists in parallel", depends_on=["build_context"], kind="parallel", details={"agents": list(tasks), "capabilities": [cap.value for cap in capabilities], "join_policy": "Wait for results, retaining unavailable evidence explicitly"}):
        outputs = audit.run_parallel(tasks, input_summary={"holdings_count": len(snapshot.holdings), "visible_transaction_count": len(snapshot.transactions), "objective": request.objective.value, "shared_snapshot": True, "identities_required_by_llm": False})
    bundle = outputs["equity_agent"]
    analysis = bundle.get("analysis")
    if analysis is None:
        analysis = SimpleAllocatorAnalyzer().analyze(context, capabilities=capabilities)
    holding_market_data = bundle.get("holding_market_data") or {"available": False, "holdings": []}
    tax_intelligence, fd_intelligence = outputs["tax_agent"], outputs["fd_agent"]
    tax_intelligence["tax_implications_for_recommendations"] = tax_impact_for_actions(tax_intelligence, list(analysis.recommended_actions or []))
    fd_intelligence["fd_implications_for_recommendations"] = fd_impact_for_actions(fd_intelligence, list(analysis.recommended_actions or []))
    trajectory_intelligence = outputs["trajectory_agent"]
    mutual_fund_intelligence = outputs["mutual_fund_agent"]

    with audit.stage("reconcile_specialists", "Check costs, tax coverage, goals and shared budgets", depends_on=["parallel_specialists"], details={"policy": policy}):
        reconcile_portfolio_analysis(analysis, mutual_fund_intelligence)
        mutual_fund_intelligence["action_checks"] = evaluate_mutual_fund_action_checks(context.twin, mutual_fund_intelligence, transactions=transactions, tax_payload=tax_intelligence, fd_payload=fd_intelligence)
        # The goal worker runs independently; only its tax-dependent score is
        # recomputed after the join. No repeated network or database request.
        if trajectory_intelligence.get("available"):
            from ai_cio.services.trajectory.score import build_trajectory_score
            trajectory_intelligence["score"] = build_trajectory_score(snapshot=trajectory_intelligence.get("snapshot") or {}, goal_rows=trajectory_intelligence.get("goal_projections") or [], behavior=trajectory_intelligence.get("behavior") or {}, portfolio_health=dict(getattr(analysis, "portfolio_health", None) or {}), tax_summary=tax_intelligence if tax_intelligence.get("available") else None)
            trajectory_intelligence["reconciliation"] = "Tax-dependent score reconciled after parallel workers joined; projection returns remain explicit scenarios."
        evaluations = evaluate_strategies(context, analysis.candidate_strategies)
        selected, alternatives = _pick_strategy(analysis.candidate_strategies, evaluations)
        goal_ids = parse_goal_ids(request.constraints)
        goal_likelihood = assess_selected_goals(context.twin, goal_ids) if goal_ids else []
        audit.check("shared_snapshot", True, "All specialists used independent copies of the same user-scoped financial snapshot; SQL sessions stayed on the request thread.")
        audit.check("contribution_ceiling", True, "New contributions require declared willingness, cashflow capacity and confirmed earmarks. The same total ceiling cannot independently fund each specialist.")
        audit.check("mf_switch_cost_coverage", True, "MF switch tax is withheld unless supported lot-mapped estimates exist; current-year realized tax is not a switch estimate.")

    sector_opportunity = {"available": False, "reason": "disabled", "recommendations": []}
    sector_day_changes = {"available": False, "sectors": [], "doing_well": [], "doing_poorly": []}
    with audit.stage("market_context", "Attach dated sector context", depends_on=["parallel_specialists"]):
        if settings.SECTOR_OPPORTUNITY_ENABLED:
            try:
                sector_opportunity = build_sector_opportunity(context.twin, sector_allocation=list(getattr(analysis, "sector_allocation", None) or []), true_exposure=dict(getattr(analysis, "true_exposure", None) or {}))
            except Exception as exc:
                sector_opportunity = {"available": False, "reason": f"Market context unavailable ({type(exc).__name__})", "recommendations": []}
        try:
            sector_day_changes = fetch_sector_day_changes()
        except Exception as exc:
            sector_day_changes["reason"] = f"Sector context unavailable ({type(exc).__name__})"

    assumptions = list(analysis.assumptions or []) + ["MF statistics use dated NAV/disclosure evidence; historical returns are not forecasts.", "FD comparisons use dated official bank terms, not guaranteed future renewal rates.", "Specialist outputs are reconciled before final action ranking."]
    stages.append("validate")
    decision_text = analysis.decision_summary or _decision_label(request.objective, selected)
    assumptions = list(dict.fromkeys(assumptions))
    if goal_likelihood:
        assumptions.append(
            "Selected-goal scenarios require an agreed uncommitted contribution ceiling; several goals need distinct allocations rather than repeating that ceiling. Returns are illustrative, not outcome probabilities."
        )
    if sector_opportunity.get("available"):
        assumptions.append(
            "Sector opportunity ranks are rule-based from Dhan index history + Twin exposure — not AI rankings."
        )
    if tax_intelligence.get("available"):
        assumptions.append(
            f"Tax figures use deterministic rule version "
            f"{tax_intelligence.get('rule_version', 'unknown')} — analytical estimates, not tax advice."
        )
    if fd_intelligence.get("available"):
        assumptions.append(
            "FD comparisons use dated official bank terms; confirm eligibility, tenor and current booking terms with the bank."
        )
    if trajectory_intelligence.get("available"):
        assumptions.append(
            "Financial trajectory uses illustrative conservative/base/optimistic return scenarios with monthly contributions — not predictions."
        )
        for action in (trajectory_intelligence.get("recommended_actions") or [])[:2]:
            if action and action not in (analysis.recommended_actions or []):
                analysis.recommended_actions = list(analysis.recommended_actions or []) + [action]

    if sector_day_changes.get("available"):
        assumptions.append("Dated sector movement is short-term context, not a fund performance forecast.")

    preliminary = DecisionResult(
        decision_id=request.decision_id,
        user_id=request.user_id,
        objective=request.objective,
        decision=decision_text,
        selected_strategy=selected,
        alternatives=alternatives,
        rationale=analysis.observations,
        key_factors=_key_factors(context, evaluations, analysis),
        risks=analysis.risks,
        tradeoffs=analysis.tradeoffs,
        assumptions=assumptions,
        evidence=analysis.evidence,
        strategy_evaluations=evaluations,
        validation=ValidationResult(passed=True),
        confidence=_confidence(context, analysis.missing_information, analysis),
        context_summary=context.to_dict(),
        recommended_actions=list(analysis.recommended_actions or []),
        insight_cards=list(getattr(analysis, "insight_cards", None) or []),
        style_allocation=list(getattr(analysis, "style_allocation", None) or []),
        sector_allocation=list(getattr(analysis, "sector_allocation", None) or []),
        portfolio_health=dict(getattr(analysis, "portfolio_health", None) or {}),
        top_worries=list(getattr(analysis, "top_worries", None) or []),
        concentration_analysis=dict(getattr(analysis, "concentration_analysis", None) or {}),
        true_exposure=dict(getattr(analysis, "true_exposure", None) or {}),
        quality_valuation=dict(getattr(analysis, "quality_valuation", None) or {}),
        goal_likelihood=goal_likelihood,
        sector_opportunity=sector_opportunity,
        suggestions={},
        tax_intelligence=tax_intelligence,
        fd_intelligence=fd_intelligence,
        trajectory_intelligence=trajectory_intelligence,
        sector_day_changes=sector_day_changes,
        holding_market_data=holding_market_data,
        mutual_fund_intelligence=mutual_fund_intelligence,
    )
    with audit.stage("validate_strategy", "Validate strategy amounts and request constraints", depends_on=["reconcile_specialists"]):
        validation = validate_decision(request, preliminary)
        preliminary.validation = validation
        audit.check("strategy_validation", validation.passed, "; ".join(validation.errors) or "Deterministic request/strategy checks passed; this does not establish future returns.")
        if not validation.passed:
            raise DecisionValidationError("; ".join(validation.errors))

    with audit.stage("synthesize_findings", "Apply skill rules, remove repetition and rank supported actions", depends_on=["validate_strategy"], details={"method": "Facts and calculations are linked to exact skill sections before ranking. Specialist suggestions are reconciled against cashflow, goals and known costs."}):
        stages.append("suggestions")
        try:
            suggestions = build_decision_suggestions(
                twin=context.twin,
                analysis_bits={
                    "portfolio_health": dict(getattr(analysis, "portfolio_health", None) or {}),
                    "top_worries": list(getattr(analysis, "top_worries", None) or []),
                    "recommended_actions": list(analysis.recommended_actions or []),
                    "holding_market_data": holding_market_data,
                    "mutual_fund_intelligence": mutual_fund_intelligence,
                    "specialist_checks": {"tax": tax_intelligence, "fixed_deposits": fd_intelligence, "trajectory": trajectory_intelligence, "mutual_funds": mutual_fund_intelligence},
                },
                sector_opportunity=sector_opportunity,
                goal_likelihood=goal_likelihood,
            )
        except Exception as exc:
            logger.warning("suggestions_failed err=%s", exc)
            suggestions = {"available": False, "items": [], "reason": type(exc).__name__, "summary": "The evidence-backed review could not complete. Refresh the data and review the missing inputs before adopting an action.", "explanation_version": "applied-principles-v1"}

        grounded = list(suggestions.get("items") or [])
        if suggestions.get("explanation_version") == "applied-principles-v1":
            proof_checks = [validate_review_proof(row) for row in grounded]
            audit.check("applied_skill_proofs", all(check["passed"] for check in proof_checks), f"Verified exact skill sections, source-file hashes and supported arithmetic for {len(proof_checks)} findings.")
            suggestions["validation"] = proof_checks
            if not all(check["passed"] for check in proof_checks):
                raise DecisionValidationError("A published finding failed proof integrity or deterministic arithmetic validation")
        preliminary.suggestions = suggestions
        if suggestions.get("explanation_version") == "applied-principles-v1":
            preliminary.decision = suggestions["summary"]
            preliminary.recommended_actions = [f"{row['action']['label']}: {row['action']['why']}" for row in grounded]
            preliminary.rationale = [row["proof"]["conclusion"] for row in grounded]
            preliminary.top_worries = [{"title": row["title"], "detail": row["detail"], "severity": "high" if row["priority_score"] >= 90 else "medium"} for row in grounded[:4]]
            preliminary.key_factors = [row["title"] for row in grounded[:4]]
            preliminary.context_summary["explanation_version"] = "applied-principles-v1"
            preliminary.tax_intelligence["tax_implications_for_recommendations"] = tax_impact_for_actions(preliminary.tax_intelligence, preliminary.recommended_actions)
            preliminary.fd_intelligence["fd_implications_for_recommendations"] = fd_impact_for_actions(preliminary.fd_intelligence, preliminary.recommended_actions)
            from domain.decision.contracts import Evidence
            applied = {p["id"]: p for row in grounded for p in row["proof"]["principles"]}
            preliminary.evidence = [Evidence(source="applied_skill",section=p["section"],reference=f"{p['path']}#L{p['line_start']}-L{p['line_end']}",
                content=p["excerpt"],relevance="Exact section excerpt matched to a published finding; see its inputs and calculation") for p in applied.values()]

    with audit.stage("central_explanation", "Explain validated findings with the configured model", depends_on=["synthesize_findings"], kind="optional_llm"):
        central_explanation = explain_validated_findings(audit, grounded, specialist_statuses=[{"id": row["id"], "status": row["status"], "output": row.get("output_summary")} for row in audit.agents], constraint_policy=policy)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    preliminary.execution = {
        "stages": stages,
        "capabilities": [cap.value for cap in capabilities],
        "duration_ms": elapsed_ms,
        "analyzer": type(decision_analyzer).__name__,
        "agent": getattr(decision_analyzer, "name", type(decision_analyzer).__name__),
        "focus": (
            "counterfactuals"
            if request.objective == DecisionObjective.EXPLORE_COUNTERFACTUALS
            else ("equity" if request.objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO else "general")
        ),
    }

    stages.append("decision_trace")
    twin_dict = context.twin if isinstance(context.twin, dict) else {}
    preliminary.agent_perspectives = build_agent_perspectives(
        grounded_reviews=grounded,
        analysis_agent=preliminary.execution.get("agent"),
        analysis_focus=preliminary.execution.get("focus"),
        decision=preliminary.decision,
        top_worries=list(preliminary.top_worries or []),
        recommended_actions=list(preliminary.recommended_actions or []),
        tax_intelligence=preliminary.tax_intelligence or {},
        fd_intelligence=preliminary.fd_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        sector_opportunity=preliminary.sector_opportunity or {},
        goal_likelihood=list(preliminary.goal_likelihood or []),
        tradeoffs=list(preliminary.tradeoffs or []),
        risks=list(preliminary.risks or []),
    )
    preliminary.decision_trace = build_decision_trace(
        grounded_reviews=grounded,
        decision=preliminary.decision,
        confidence=preliminary.confidence,
        key_factors=list(preliminary.key_factors or []),
        rationale=list(preliminary.rationale or []),
        assumptions=list(preliminary.assumptions or []),
        risks=list(preliminary.risks or []),
        tradeoffs=list(preliminary.tradeoffs or []),
        recommended_actions=list(preliminary.recommended_actions or []),
        top_worries=list(preliminary.top_worries or []),
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
        true_exposure=dict(preliminary.true_exposure or {}),
        tax_intelligence=preliminary.tax_intelligence or {},
        fd_intelligence=preliminary.fd_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        sector_opportunity=preliminary.sector_opportunity or {},
        goal_likelihood=list(preliminary.goal_likelihood or []),
        execution=preliminary.execution,
        twin=twin_dict,
    )
    # Prefer perspectives already embedded in the trace to keep cards identical
    preliminary.agent_perspectives = {
        **preliminary.agent_perspectives,
        "agents": (preliminary.decision_trace.get("steps") or {}).get("specialist_findings")
        or preliminary.agent_perspectives.get("agents"),
    }
    preliminary.temporal_changes = build_temporal_changes(twin_dict)
    preliminary.behavioral_intelligence = build_behavioral_intelligence(
        twin=twin_dict,
        observed_behavior=(preliminary.trajectory_intelligence or {}).get("behavior"),
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
    )
    preliminary.data_quality = build_data_quality_report(
        twin=twin_dict,
        tax_intelligence=preliminary.tax_intelligence or {},
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
    )
    preliminary.counterfactuals = build_counterfactuals(
        twin=twin_dict,
        tax_intelligence=preliminary.tax_intelligence or {},
        trajectory_intelligence=preliminary.trajectory_intelligence or {},
        concentration_analysis=dict(preliminary.concentration_analysis or {}),
    )
    # AI narrates / ranks deterministic scenarios — does not recompute maths.
    if preliminary.counterfactuals.get("available") and request.objective == DecisionObjective.EXPLORE_COUNTERFACTUALS:
        with audit.scope("counterfactual_explanation"):
            preliminary.counterfactuals = enrich_counterfactuals_with_ai(
                preliminary.counterfactuals,
                twin=twin_dict,
                decision=preliminary.decision,
                top_worries=list(preliminary.top_worries or []),
                recommended_actions=list(preliminary.recommended_actions or []),
                behavioural=preliminary.behavioral_intelligence or {},
            )

    if grounded:
        links = [{"id": row["id"], "title": row["topic_label"], "href": f"#review-{row['id']}"} for row in grounded]
        preliminary.counterfactuals["evidence_links"] = links
        for scenario in preliminary.counterfactuals.get("scenarios", []):
            key = str(scenario.get("id") or "")
            relevant = {"equity-exposure", "tax-coverage"} if "trim" in key or "tax" in key else {"joint-goal-budget", "liquidity-earmark", "retirement-basis"}
            scenario["evidence_links"] = [link for link in links if link["id"] in relevant]

    logger.info(
        "decision_complete decision_id=%s user_id=%s objective=%s analyzer=%s duration_ms=%s "
        "agents=%s disagreements=%s temporal=%s",
        request.decision_id,
        request.user_id,
        request.objective.value,
        type(decision_analyzer).__name__,
        elapsed_ms,
        len((preliminary.agent_perspectives or {}).get("agents") or []),
        len((preliminary.agent_perspectives or {}).get("disagreements") or []),
        bool((preliminary.temporal_changes or {}).get("available")),
    )

    with audit.stage("publish", "Publish one coherent decision and its audit trail", depends_on=["central_explanation"]):
        final_validation = validate_decision(request, preliminary)
        audit.check("final_publication", final_validation.passed, "; ".join(final_validation.errors) or "Final canonical result passed the strategy checks after synthesis. No model-generated amount replaces deterministic arithmetic.")
        if not final_validation.passed:
            raise DecisionValidationError("; ".join(final_validation.errors))
        preliminary.validation = final_validation
        preliminary.context_summary["contribution_policy"] = policy
    preliminary.orchestration = audit.export(grounded=grounded)
    preliminary.orchestration["constraint_policy"] = policy
    preliminary.orchestration["synthesis"] = central_explanation
    preliminary.execution["duration_ms"] = preliminary.orchestration["duration_ms"]
    preliminary.execution["parallel_specialists"] = [row["id"] for row in audit.agents]
    preliminary.execution["llm_calls"] = len(audit.llm_calls)
    return preliminary.to_dict()


def _pick_strategy(strategies, evaluations):
    if not strategies:
        return None, []
    if not evaluations:
        return strategies[0], strategies[1:]

    ranked = sorted(
        evaluations,
        key=lambda item: (len(item.conflicts), len(item.weaknesses), -len(item.strengths)),
    )
    best_name = ranked[0].strategy.name
    selected = next(s for s in strategies if s.name == best_name)
    alternatives = [s for s in strategies if s is not selected]
    return selected, alternatives


def _decision_label(objective: DecisionObjective, selected) -> str:
    if objective == DecisionObjective.ALLOCATE_CAPITAL and selected:
        return f"Review a {selected.name.lower()} allocation split for the available capital."
    if objective == DecisionObjective.REVIEW_PORTFOLIO:
        return "Review portfolio fit against goals, concentration, and risk factors."
    if objective == DecisionObjective.EVALUATE_PORTFOLIO_RISK:
        return "Review portfolio risk using willingness, capacity, and holdings together."
    if objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO:
        return "Review your equity sleeve for concentration, suitability, and next actions."
    if objective == DecisionObjective.REVIEW_MUTUAL_FUND_PORTFOLIO:
        return "Review mutual fund growth, benchmark evidence, overlap, costs and suitability."
    if objective == DecisionObjective.EXPLORE_COUNTERFACTUALS:
        return "Compare current path vs alternate what-if paths (trim, contributions, tax harvest, emergency cash)."
    return "Review the decision factors below. This is not a buy or sell instruction."


def _key_factors(context, evaluations, analysis=None) -> list[str]:
    factors = [f"Objective: {context.objective.value}"]
    if analysis is not None:
        for item in getattr(analysis, "recommended_actions", [])[:2]:
            factors.append(f"Action: {item}")
        raw = None
        # Prefer model key_factors if present on strategy characteristics — skip
    if context.missing_optional:
        factors.append(f"Optional gaps: {', '.join(context.missing_optional)}")
    for evaluation in evaluations[:2]:
        for conflict in evaluation.conflicts:
            factors.append(conflict)
    return factors


def _confidence(context, missing: list[str], analysis=None) -> str:
    if analysis is not None and analysis.candidate_strategies:
        hinted = (analysis.candidate_strategies[0].expected_characteristics or {}).get("confidence")
        if hinted in {"low", "medium", "high"}:
            return hinted
    score = sum(1 for value in (context.completeness or {}).values() if value)
    if missing:
        score -= 1
    if score >= 5:
        return "medium"
    if score >= 3:
        return "low"
    return "low"
