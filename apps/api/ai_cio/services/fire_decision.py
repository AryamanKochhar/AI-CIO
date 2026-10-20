"""Publish a saved FIRE goal as a deterministic, user-scoped decision.

This path never fetches market prices or asks a language model to invent a plan.
"""
from __future__ import annotations

from time import perf_counter

from ai_cio.services import goals as goal_svc
from ai_cio.services import twin as twin_svc
from ai_cio.services.fire_planner import build_fire_plan
from ai_cio.services.instruments import DomainError
from domain.decision.contracts import DecisionResult, Evidence, ValidationResult


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
    if "fire_inputs" in (request.constraints or {}):
        raise DomainError("Save the FIRE assumptions as a goal before running a decision")
    goal = _selected_goal(goal_svc.list_goals(db, request.user_id), request.constraints)
    twin = twin_svc.assemble_twin(db, request.user_id)
    plan = build_fire_plan(twin, goal.planning_inputs)
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
        execution={"agent":"DeterministicFirePlanner", "analyzer":"DeterministicFirePlanner", "focus":"fire", "stages":["load_saved_fire_goal","assemble_twin","calculate_fire_path","apply_psychometric_policy","compare_fd_terms"], "duration_ms":int((perf_counter()-began)*1000)},
    )
    return result.to_dict()
