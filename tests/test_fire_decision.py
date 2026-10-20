"""FIRE API and decision integration, persistence scope and cache invalidation."""
from types import SimpleNamespace

import pytest

from ai_cio.services import goals, identity
from ai_cio.services.decision_cache import compute_input_fingerprint
from ai_cio.services.fire_decision import _selected_goal
from ai_cio.services.instruments import DomainError
from ai_cio.db.models import Goal
from domain.decision.contracts import DecisionRequest


def inputs():
    return {"current_age":35,"retirement_age":65,"monthly_spending_today":40000,
            "monthly_investment_budget":30000,"annual_pension_today":0,"earmarked_assets":500000}


def create(db,user):
    row=goals.create_goal(db,user.id,{"name":"Financial independence by 65","goal_type":"fire","planning_inputs":inputs()})
    db.commit()
    return row


@pytest.mark.parametrize("selection", [[True],[1.5],[0],[-1],[],[1,2],"1"])
def test_fire_requires_exactly_one_valid_selected_goal(selection):
    row=SimpleNamespace(id=1,goal_type="fire",planning_inputs=inputs())
    with pytest.raises(DomainError,match="exactly one"):
        _selected_goal([row],{"goal_ids":selection})


def test_fire_rejects_ambiguous_and_missing_saved_assumptions():
    a=SimpleNamespace(id=1,goal_type="fire",planning_inputs=inputs())
    b=SimpleNamespace(id=2,goal_type="fire",planning_inputs=inputs())
    with pytest.raises(DomainError,match="exactly one"):
        _selected_goal([a,b],{})
    a.planning_inputs=None
    with pytest.raises(DomainError,match="assumptions"):
        _selected_goal([a],{})


def test_fire_preview_is_read_only_and_returns_user_input_limits(client,db):
    user=identity.create_user(db,"FIRE preview fixture")
    db.commit()
    before=db.query(Goal).count()
    response=client.post(f"/users/{user.id}/fire/preview",json=inputs())
    assert response.status_code==200, response.text
    assert response.headers["cache-control"]=="private, no-store"
    assert response.json()["psychometric_application"]
    assert db.query(Goal).count()==before
    assert client.post("/users/999999/fire/preview",json=inputs()).status_code==404


def test_saved_fire_update_persists_and_invalidates_decision_fingerprint(client,db):
    user=identity.create_user(db,"FIRE saved fixture")
    row=create(db,user)
    request=DecisionRequest.from_payload(user_id=user.id,objective="plan_fire",constraints={"goal_ids":[row.id]})
    before=compute_input_fingerprint(db,user.id,request)
    data={"name":row.name,"goal_type":"fire","planning_inputs":{**inputs(),"monthly_investment_budget":35000}}
    response=client.put(f"/users/{user.id}/goals/{row.id}",json=data)
    assert response.status_code==200,response.text
    assert response.json()["planning_inputs"]["monthly_investment_budget"]==35000
    db.expire_all()
    assert compute_input_fingerprint(db,user.id,request)!=before
    assert db.query(Goal).filter(Goal.user_id==user.id).count()==1


def test_fire_cannot_select_another_users_goal(client,db):
    owner=identity.create_user(db,"FIRE owner")
    other=identity.create_user(db,"FIRE other")
    row=create(db,owner)
    result=client.post(f"/users/{other.id}/decisions",json={"objective":"plan_fire","constraints":{"goal_ids":[row.id]}})
    assert result.status_code==400,result.text
    assert "exactly one" in result.json()["detail"]
    update=client.put(f"/users/{other.id}/goals/{row.id}",json={"name":"forbidden","goal_type":"fire","planning_inputs":inputs()})
    assert update.status_code==404


def test_fire_decision_uses_saved_goal_without_generic_agents(client,db,monkeypatch):
    from ai_cio.services.orchestration import coordinator
    user=identity.create_user(db,"FIRE decision fixture")
    row=create(db,user)
    def forbidden(*args,**kwargs):
        raise AssertionError("FIRE must not fetch market data or run the generic equity pipeline")
    monkeypatch.setattr(coordinator,"build_investment_context",forbidden)
    monkeypatch.setattr(coordinator,"build_holding_market_data",forbidden)
    response=client.post(f"/users/{user.id}/decisions",json={"objective":"plan_fire","constraints":{"goal_ids":[row.id]}})
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload["fire_plan"]["goal_id"]==row.id
    assert payload["execution"]["agent"]=="DeterministicFirePlanner"
    assert payload["context_summary"]["outcome_probabilities_estimated"] is False
    assert len(payload["orchestration"]["agents"]) == 6
    assert "bond_agent" in {agent["id"] for agent in payload["orchestration"]["agents"]}
    assert payload["bond_intelligence"]["central_checks"]["execution_allowed"] is False
    assert "not added" in payload["mutual_fund_intelligence"]["fire_context"]
    assert payload["cache"]["hit"] is False
    again=client.post(f"/users/{user.id}/decisions",json={"objective":"plan_fire","constraints":{"goal_ids":[row.id]}})
    assert again.status_code==200 and again.json()["cache"]["hit"] is True
