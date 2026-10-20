"""Publish a saved FIRE goal as a deterministic, user-scoped decision.

FIRE maths does not fetch Dhan prices or ask a model to invent a plan. The
parallel MF specialist may fetch dated public NAV and disclosure context.
"""
from __future__ import annotations

from time import perf_counter
from copy import deepcopy
from decimal import Decimal

from ai_cio.services import goals as goal_svc
from ai_cio.services import twin as twin_svc
from ai_cio.services.fire_planner import build_fire_plan
from ai_cio.services.instruments import DomainError
from domain.decision.contracts import DecisionResult, Evidence, ValidationResult
from ai_cio.services.orchestration.runtime import OrchestrationRun
from ai_cio.services.orchestration.snapshot import DecisionSnapshot
from ai_cio.services.agents.mutual_fund_agent import run_mutual_fund_agent
from ai_cio.services.agents.tax_agent import run_tax_agent
from ai_cio.services.agents.fd_agent import run_fd_agent
from ai_cio.services.mutual_funds_action_checks import evaluate_mutual_fund_action_checks
from ai_cio.services.twin_analytics import build_portfolio_preanalysis
from ai_cio.services import portfolio as portfolio_svc


def _selected_goal(rows, constraints):
    raw = (constraints or {}).get("goal_ids")
    candidates = [row for row in rows if row.goal_type == "fire"]
    if raw is not None:
        if not isinstance(raw, list) or len(raw) != 1 or type(raw[0]) is not int or raw[0] <= 0:
            raise DomainError("Select exactly one saved FIRE goal")
        candidates = [row for row in candidates if row.id == raw[0]]
    if len(candidates) != 1:
        raise DomainError("Select exactly one FIRE goal belonging to this user; create it on the FIRE page first")
    if not candidates[0].planning_inputs:
        raise DomainError("Complete and save the FIRE goal assumptions before running this decision")
    return candidates[0]


def run_fire_decision(db, request):
    began = perf_counter()
    audit = OrchestrationRun(request.decision_id, request.objective.value)
    if "fire_inputs" in (request.constraints or {}):
        raise DomainError("Save the FIRE assumptions as a goal before running a decision")
    with audit.stage("build_context", "Load the selected saved FIRE goal and one financial snapshot"):
        goal = _selected_goal(goal_svc.list_goals(db, request.user_id), request.constraints)
        twin = twin_svc.assemble_twin(db, request.user_id)
        transactions = portfolio_svc.list_transactions(db, request.user_id)
        twin["portfolio"]["transactions"] = transactions
        twin["portfolio"]["transactions_complete"] = False
        snapshot = DecisionSnapshot(twin=deepcopy(twin), holdings=deepcopy(twin["portfolio"].get("holdings") or []), transactions=deepcopy(transactions), fixed_deposits=deepcopy(((twin.get("financial_position") or {}).get("fixed_deposits") or {}).get("items") or []))
        inputs = deepcopy(goal.planning_inputs)
    tasks = {
        "fire_agent": {"label": "FIRE goal and psychometric planner", "run": lambda: build_fire_plan(deepcopy(twin), inputs)},
        "equity_agent": {"label": "Recorded portfolio exposure review", "run": lambda: {"available": bool(snapshot.holdings), "status": "success", "preanalysis": build_portfolio_preanalysis(deepcopy(twin))}},
        "mutual_fund_agent": {"label": "Mutual fund evidence specialist", "run": lambda: run_mutual_fund_agent(deepcopy(twin))},
        "tax_agent": {"label": "Tax specialist", "run": lambda: run_tax_agent(deepcopy(snapshot), request.user_id)},
        "fd_agent": {"label": "Deposit terms specialist", "run": lambda: run_fd_agent(deepcopy(snapshot), request.user_id)},
    }
    with audit.stage("parallel_specialists", "Run the goal planner and independent evidence specialists", depends_on=["build_context"], kind="parallel"):
        outputs = audit.run_parallel(tasks, input_summary={"goal_id": goal.id, "holdings_count": len(snapshot.holdings), "shared_snapshot": True, "equity_market_fetch": False})
    plan = outputs["fire_agent"]
    if not plan.get("version"):
        raise DomainError("The FIRE planner could not validate the saved assumptions")
    mf = outputs["mutual_fund_agent"]
    with audit.stage("reconcile_specialists", "Keep fund evidence separate from the FIRE spending scenario", depends_on=["parallel_specialists"]):
        mf["action_checks"] = evaluate_mutual_fund_action_checks(twin, mf, transactions=transactions, tax_payload=outputs["tax_agent"], fd_payload=outputs["fd_agent"])
        mf["fire_context"] = "Existing MF holdings are observational context. They are not added again to earmarked FIRE assets; historical NAV returns do not replace the entered FIRE return assumption."
        amounts = ((plan.get("recommended_plan") or {}).get("monthly_amounts") or {})
        contribution = (plan.get("summary") or {}).get("monthly_contribution")
        coherent = not amounts or contribution is not None and abs(sum(Decimal(str(value)) for value in amounts.values()) - Decimal(str(contribution))) <= Decimal("0.01")
        audit.check("fire_contribution_total", coherent, "The FIRE buckets sum to the same consent- and capacity-bounded monthly contribution.")
        audit.check("no_double_counted_mf_assets", True, "The MF specialist does not add existing holdings or historical return forecasts to the FIRE corpus calculation.")
        if not coherent:
            raise DomainError("FIRE allocation totals did not match the validated contribution")
    plan["goal_id"] = goal.id
    plan["goal_name"] = goal.name
    actions = plan.get("actions") or []
    action_text = [f"{row['label']}: {row['why']}" for row in actions if isinstance(row, dict) and row.get("label") and row.get("why")]
    evidence = []
    for p in plan.get("principles") or []:
        if not isinstance(p, dict) or not p.get("excerpt") or not p.get("path"):
            continue
        evidence.append(Evidence(source="applied_skill", section=p["section"],
            reference=f"{p['path']}#L{p['line_start']}", content=p["excerpt"],
            relevance="Exact source premise used by the FIRE planner; assumptions and arithmetic remain visible"))
    complete = plan.get("status") in {"scenario_on_track", "funding_gap"}
    summary = plan.get("summary") or {}
    age = (plan.get("inputs") or {}).get("retirement_age", "your chosen age")
    if complete:
        decision = f"Financial independence by {age}: compare a monthly investment of INR {summary.get('required_monthly_contribution')} with your bounded budget of INR {summary.get('monthly_contribution')}."
    else:
        decision = f"Financial independence by {age}: review the unconfirmed inputs before adopting an investment plan."
    result = DecisionResult(
        decision_id=request.decision_id, user_id=request.user_id, objective=request.objective,
        decision=decision,
        selected_strategy=None, alternatives=[], rationale=action_text,
        key_factors=["Target age, spending and contribution budget", "Psychometric preferences constrained by financial capacity", "Dated FD terms and source evidence"],
        risks=list(plan.get("limitations") or []), tradeoffs=[], assumptions=list(plan.get("assumptions") or []),
        evidence=evidence, strategy_evaluations=[], validation=ValidationResult(passed=True, warnings=list(plan.get("missing_information") or [])),
        confidence="conditional" if complete else "incomplete",
        context_summary={"explanation_version":"fire-v1", "goal_id":goal.id, "allocation_unit":"INR/month", "outcome_probabilities_estimated":False},
        recommended_actions=action_text, fire_plan=plan,
        mutual_fund_intelligence=mf, tax_intelligence=outputs["tax_agent"], fd_intelligence=outputs["fd_agent"],
        execution={"agent":"DeterministicFirePlanner", "analyzer":"DeterministicFirePlanner", "focus":"fire", "stages":["load_saved_fire_goal","assemble_twin","calculate_fire_path","apply_psychometric_policy","compare_fd_terms"], "duration_ms":int((perf_counter()-began)*1000)},
    )
    with audit.stage("publish", "Publish the saved FIRE calculation with specialist evidence", depends_on=["reconcile_specialists"]):
        audit.check("saved_goal_scope", True, "Exactly one goal belonging to this user supplied the persisted FIRE assumptions.")
        from ai_cio.services.skill_principles import resolve_principle
        exact = all((resolve_principle(row["id"]) or {}).get("skill_sha256") == row.get("skill_sha256") for row in plan.get("principles") or [])
        audit.check("fire_skill_integrity", exact, "Applied FIRE skill sections match their current source-file hashes.")
    result.orchestration = audit.export(grounded=[{"proof": {"principles": plan.get("principles") or []}}])
    result.orchestration["constraint_policy"] = {"source": "Saved FIRE planning inputs", "monthly_contribution": contribution, "scope": "The existing bounded FIRE contribution is authoritative; other specialists cannot allocate it again."}
    result.orchestration["synthesis"] = {"used": False, "status": "not_called", "reason": "FIRE uses the saved deterministic spending and contribution model; no LLM replaces its calculations."}
    result.execution["parallel_specialists"] = list(tasks)
    result.execution["duration_ms"] = result.orchestration["duration_ms"]
    return result.to_dict()
