"""Execution, transport and constraint invariants for the central coordinator."""
from copy import deepcopy
import json
from threading import Barrier
from types import SimpleNamespace

import pytest

from ai_cio.services.orchestration.policy import contribution_policy, validate_review_proof
from ai_cio.services.orchestration.runtime import OrchestrationRun, sanitize_llm_messages


def test_five_specialists_really_start_before_any_join():
    barrier = Barrier(5, timeout=5)
    run = OrchestrationRun("parallel-proof", "review_portfolio")
    def worker(name):
        barrier.wait()
        return {"available": True, "status": "success", "findings": [{"name": name}]}
    ids = ["equity_agent", "mutual_fund_agent", "tax_agent", "fd_agent", "trajectory_agent"]
    outputs = run.run_parallel({name: {"label": name, "run": lambda name=name: worker(name)} for name in ids}, input_summary={"shared_snapshot": True})
    assert list(outputs) == ids
    assert all(output["available"] for output in outputs.values())
    assert max(row["started_at"] for row in run.agents) < min(row["finished_at"] for row in run.agents)
    assert all(row["duration_ms"] >= 0 for row in run.agents)
    assert all(len(row["resource_pack"]["source_ids"]) >= 6 for row in run.agents)


def test_failed_worker_does_not_fabricate_or_cancel_other_results():
    run = OrchestrationRun("failure-proof", "review_portfolio")
    def fail():
        raise ValueError("private provider response must not enter receipts")
    outputs = run.run_parallel({"mutual_fund_agent": {"label": "MF", "run": fail}, "fd_agent": {"label": "FD", "run": lambda: {"available": True}}}, input_summary={})
    assert outputs["mutual_fund_agent"]["available"] is False
    assert outputs["fd_agent"]["available"] is True
    assert "private provider" not in json.dumps(run.export())
    assert run.export()["status"] == "partial"
    assert run.export()["llm_calls"] == []


@pytest.mark.parametrize("budget,surplus,expected", [(30000,20000,"20000.00"),(10000,20000,"10000.00"),(0,20000,"0.00"),(10000,-5000,"0.00")])
def test_monthly_ceiling_uses_both_consent_and_capacity(budget,surplus,expected):
    twin={"financial_position":{"income":{"value":"50000"},"expenses":{"value":str(50000-surplus)},"cashflow_cadence":"monthly"}}
    policy=contribution_policy(twin,{"monthly_investment_budget":budget,"other_goal_monthly_commitments":0,"reserve_monthly_commitment":0})
    assert policy["total_monthly_ceiling"] == expected
    assert policy["uncommitted_monthly_ceiling"] == expected


@pytest.mark.parametrize("budget", [None,True,"NaN","Infinity",-1])
def test_no_consent_is_not_an_instruction_to_invest_surplus(budget):
    twin={"financial_position":{"income":{"value":"50000"},"expenses":{"value":"20000"},"cashflow_cadence":"monthly"}}
    assert contribution_policy(twin,{"monthly_investment_budget":budget})["uncommitted_monthly_ceiling"] is None


def test_joint_earmarks_are_subtracted_once_and_never_assumed_confirmed():
    twin={"financial_position":{"income":{"value":"50000"},"expenses":{"value":"20000"},"cashflow_cadence":"monthly"}}
    assert contribution_policy(twin,{"monthly_investment_budget":25000})["uncommitted_monthly_ceiling"] is None
    policy=contribution_policy(twin,{"monthly_investment_budget":25000,"other_goal_monthly_commitments":10000,"reserve_monthly_commitment":5000})
    assert policy["uncommitted_monthly_ceiling"] == "10000.00"


def test_transport_preview_is_the_body_actually_sent_without_identifiers(monkeypatch):
    from ai_cio.services.agents import openrouter_client as client
    monkeypatch.setattr(client.settings,"equity_llm_provider",lambda:"openai")
    monkeypatch.setattr(client.settings,"equity_llm_api_key",lambda:"test-only-secret")
    monkeypatch.setattr(client.settings,"equity_llm_model",lambda:"test-model")
    monkeypatch.setattr(client.settings,"equity_llm_base_url",lambda:"https://test.invalid/v1")
    captured={}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":'{"observations": []}'}}]}
    class Http:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,**kwargs):
            captured.update(kwargs)
            return Response()
    monkeypatch.setattr(client.httpx,"Client",Http)
    run=OrchestrationRun("transport-proof","review_portfolio")
    message={"role":"user","content":json.dumps({"user":{"id":42,"name":"Private Person"},"folio":"secret-folio","pan":"ABCDE1234F","email":"private@example.com","bank_account":"private-bank","demat_account":"private-demat","facts":[{"label":"Account number","value":"private-fact-account"}],"income":"50000"})}
    with run.scope("equity_agent"):
        parsed=client.extract_json_object(client.chat_completion([message]))
    assert parsed == {"observations":[]}
    call=run.export()["llm_calls"][0]
    assert call["request_preview"] == captured["json"]
    audit=json.dumps(call)
    assert all(value not in audit for value in ["Private Person","secret-folio","ABCDE1234F","private@example.com","test-only-secret","private-bank","private-demat","private-fact-account"])
    assert '50000' in audit
    assert call["validation"]["json_object"] is True
    assert call["headers_included"] is False


def test_proof_validation_detects_modified_skill_or_calculation():
    from ai_cio.services.grounded_reviews import build_grounded_reviews
    twin={"financial_position":{"income":{"value":"100000"},"expenses":{"value":"50000"},"liquid":{"value":"10000"},"cashflow_cadence":"monthly"},"portfolio":{"holdings":[]},"goals":{"items":[{"id":1,"name":"Known goal","target_amount":"300000","current_funding":"0","horizon_years":3}]}}
    twin["goals"]["items"][0]["goal_type"]="emergency"
    rows=build_grounded_reviews(twin)["items"]
    row=next(row for row in rows if row["proof"]["calculations"])
    assert validate_review_proof(row)["passed"]
    changed=deepcopy(row)
    changed["proof"]["principles"][0]["excerpt"]="A fabricated quotation"
    assert not validate_review_proof(changed)["passed"]
    changed=deepcopy(row)
    changed["proof"]["calculations"][0]["result"]="999999"
    assert not validate_review_proof(changed)["passed"]


def test_llm_central_explanation_cannot_introduce_new_numbers(monkeypatch):
    from ai_cio.services.orchestration import narrative
    monkeypatch.setattr(narrative.settings,"DECISION_SYNTHESIS_ENABLED",True)
    monkeypatch.setattr(narrative.settings,"equity_llm_configured",lambda:True)
    monkeypatch.setattr(narrative,"chat_completion",lambda *args,**kwargs:json.dumps({"summary":"Expect 20% growth","finding_explanations":[{"finding_id":"fund-proof","explanation":"Review the evidence."}]}))
    result=narrative.explain_validated_findings(OrchestrationRun("bad-narrative","review_portfolio"),[{"id":"fund-proof","title":"Review","detail":"Evidence","action":{},"proof":{}}],specialist_statuses=[],constraint_policy={})
    assert result["used"] is False and result["status"] == "rejected"
    assert result["validation"]["no_model_numbers"] is False


def test_coordinator_joins_snapshot_workers_before_final_grounding(monkeypatch):
    from ai_cio.services.orchestration import coordinator as coord
    from domain.decision.contracts import AnalysisResult, DecisionRequest
    barrier=Barrier(5,timeout=5)
    twin={"user":{"id":42},"portfolio":{"holdings":[]},"financial_position":{},"behaviour":{},"goals":{"items":[]},"completeness":{}}
    context=SimpleNamespace(twin=twin,market_context={},missing_optional=[],completeness={},to_dict=lambda:{})
    monkeypatch.setattr(coord,"build_investment_context",lambda *args,**kwargs:context)
    monkeypatch.setattr(coord.settings,"SECTOR_OPPORTUNITY_ENABLED",False)
    monkeypatch.setattr(coord.settings,"TRAJECTORY_INTELLIGENCE_ENABLED",True)
    monkeypatch.setattr(coord.settings,"MUTUAL_FUND_AGENT_ENABLED",True)
    monkeypatch.setattr(coord.settings,"DECISION_SYNTHESIS_ENABLED",False)
    monkeypatch.setattr(coord,"fetch_sector_day_changes",lambda:{"available":False})
    def specialist(snapshot,*args,**kwargs):
        assert snapshot.decision_snapshot is True
        assert not hasattr(snapshot,"query")
        barrier.wait()
        return {"available":False,"status":"insufficient_data"}
    monkeypatch.setattr(coord,"run_tax_agent",specialist)
    monkeypatch.setattr(coord,"run_fd_agent",specialist)
    monkeypatch.setattr(coord,"run_trajectory_for_user",specialist)
    def mutual(snapshot):
        assert isinstance(snapshot,dict)
        barrier.wait()
        return {"available":True,"status":"partial","funds":[],"findings":[{"id":"mf-evidence"}]}
    monkeypatch.setattr(coord,"run_mutual_fund_agent",mutual)
    received={}
    def suggestions(**kwargs):
        received.update(kwargs["analysis_bits"])
        return {"available":False,"items":[]}
    monkeypatch.setattr(coord,"build_decision_suggestions",suggestions)
    class Analyzer:
        def analyze(self,*args,**kwargs):
            barrier.wait()
            return AnalysisResult(observations=[],candidate_strategies=[],risks=[],tradeoffs=[],assumptions=[],evidence=[],missing_information=[])
    request=DecisionRequest.from_payload(user_id=42,objective="review_mutual_fund_portfolio")
    context.objective=request.objective
    output=coord.run_decision(SimpleNamespace(),request,analyzer=Analyzer())
    assert received["mutual_fund_intelligence"]["findings"][0]["id"] == "mf-evidence"
    assert len(output["orchestration"]["agents"]) == 5
    assert output["orchestration"]["validation"]["passed"] is True
    assert "synthesize_findings" in [row["id"] for row in output["orchestration"]["stages"]]
    assert output["orchestration"]["llm_calls"] == []


def test_shared_ceiling_is_not_repeated_for_each_goal():
    from ai_cio.services.goal_likelihood import assess_selected_goals
    twin={"financial_position":{"income":{"value":"100000"},"expenses":{"value":"50000"},"cashflow_cadence":"monthly"},"contribution_policy":{"uncommitted_monthly_ceiling":"10000.00"},"goals":{"items":[{"id":1,"name":"First","target_amount":"500000","current_funding":"0","horizon_years":5},{"id":2,"name":"Second","target_amount":"500000","current_funding":"0","horizon_years":5}]}}
    rows=assess_selected_goals(twin,[1,2])
    assert all(row["monthly_surplus_used"] is None for row in rows)
    assert assess_selected_goals(twin,[1])[0]["monthly_surplus_used"] == "10000.00"


def test_what_if_does_not_treat_surplus_or_liquid_reserve_as_agreed_funding():
    from ai_cio.services.counterfactuals import _contribution_scenarios, _return_assumption_scenarios
    twin={"portfolio":{"total_value":{"value":"100000"}},"financial_position":{"liquid":{"value":"50000"}}}
    traj={"snapshot":{"monthly_surplus":"50000"},"contribution_policy":{"uncommitted_monthly_ceiling":None}}
    assert _contribution_scenarios(twin=twin,traj=traj) is None
    assert _return_assumption_scenarios(twin=twin,traj=traj) is None
    traj["contribution_policy"]["uncommitted_monthly_ceiling"]="10000"
    result=_contribution_scenarios(twin=twin,traj=traj)
    assert result["actual"]["monthly_contribution"] == "10000.00"
    assert "unapproved" in " ".join(result["assumptions"])


def test_unrelated_tax_opportunity_cannot_price_a_hypothetical_trim():
    from ai_cio.services.counterfactuals import _trim_largest_holding_scenario
    result=_trim_largest_holding_scenario(twin={"portfolio":{"total_value":{"value":"100000"}}},concentration={"largest_holding_percent":"50"},tax_intelligence={"available":True,"opportunities":[{"security":"An unrelated holding","amount":"5000"}],"summary":{"stcg":"1000","estimated_tax":"200"}})
    assert result["alternatives"][0]["illustrative_tax_impact"] is None


def test_json_parsing_does_not_mean_model_content_was_accepted():
    from ai_cio.services.orchestration.runtime import note_content_validation, note_json_validation
    run=OrchestrationRun("separate-validation","review_portfolio")
    with run.scope("central_orchestrator"):
        run.begin_llm("central_orchestrator",{"model":"test","messages":[]},"test")
        note_json_validation(True)
        note_content_validation({"no_model_numbers":False},False)
    receipt=run.export()["llm_calls"][0]
    assert receipt["validation"]["json_object"] is True
    assert receipt["validation"]["accepted_as_explanation"] is False
    assert receipt["status"] == "rejected"
