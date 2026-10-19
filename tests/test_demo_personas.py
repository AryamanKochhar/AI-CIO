from decimal import Decimal

from ai_cio.db.models import AssessmentResponse, BehavioralProfile, Holding
from ai_cio.services.demo_personas import launch_persona, persona_catalogue
from ai_cio.services.journey import get_or_create_journey
from ai_cio.services.portfolio import list_holdings
from ai_cio.services.twin import assemble_twin


def test_catalogue_is_fixed_complete_and_does_not_leak_option_scores(db):
    catalogue = persona_catalogue(db)
    assert [p["id"] for p in catalogue] == ["tom", "maya", "arjun"]
    assert all(p["synthetic"] and len(p["fixed_answers"]) == 18 for p in catalogue)
    assert all("score" not in answer for p in catalogue for answer in p["fixed_answers"])
    assert persona_catalogue(db) == catalogue


def test_demo_launch_scores_canonical_answers_and_isolates_users(db):
    first = launch_persona(db, "tom")
    second = launch_persona(db, "tom")
    assert first["user"].id != second["user"].id
    assert db.query(AssessmentResponse).filter_by(session_id=first["session_id"]).count() == 18
    assert db.query(BehavioralProfile).filter_by(user_id=first["user"].id).count() == 1
    assert db.query(Holding).filter_by(user_id=first["user"].id).count() == 3
    assert len(list_holdings(db, first["user"].id)) == 3
    twin = assemble_twin(db, first["user"].id)
    assert twin["completeness"]["portfolio"] is True
    assert twin["portfolio"]["provenance"]["source"] == "Synthetic demo portfolio"
    assert Decimal(str(twin["portfolio"]["total_value"]["value"])) == Decimal("12000000")
    assert get_or_create_journey(db, first["user"].id).current_step == "analysis"


def test_persona_routes_reject_unknown_without_creating_a_user(client):
    catalogue = client.get("/demo/personas")
    assert catalogue.status_code == 200
    assert len(catalogue.json()["personas"]) == 3
    assert client.post("/demo/personas/unknown/launch").status_code == 404
    result = client.post("/demo/personas/maya/launch")
    assert result.status_code == 200
    assert result.json()["persona"]["synthetic"] is True
    assert result.json()["user"]["name"] == "Maya (synthetic demo)"

