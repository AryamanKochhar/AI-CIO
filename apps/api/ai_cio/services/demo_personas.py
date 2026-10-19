"""Transparent synthetic fixtures, scored by the normal assessment workflow.

Every launch creates an isolated user with invented finances and transactions.
Fresh, dated Dhan closes can value its real listed instruments; they do not make
the positions real. The fixed answers target instrument 1.0.
"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from ai_cio.services import assessments, identity, journey
from ai_cio.services.demo_scenarios import SCENARIOS, populate_financial_scenario
from ai_cio.services.instruments import DomainError, current_instrument

PERSONAS = (
    {"id": "tom", "name": "Tom", "description": "Dual income, no kids; approaching retirement",
     "occupation": "Indian Administrative Service (IAS)", "age": 56,
     "income": "240000", "expenses": "110000", "liquid": "1600000",
     "goal": "Retirement transition", "goal_type": "retirement", "target": "30000000",
     "funding": "12000000", "horizon": 4, "portfolio": "12000000",
     "answers": ("2", "5", "B", "4", "C", "2", "2", "B", "2", "C", "2", "4", "C", "4", "2", "B", "2", "2")},
    {"id": "maya", "name": "Maya", "description": "Early career; building a safety net and a home deposit",
     "occupation": "Software engineer", "age": 28,
     "income": "120000", "expenses": "65000", "liquid": "250000",
     "goal": "Home deposit", "goal_type": "home", "target": "2000000",
     "funding": "350000", "horizon": 5, "portfolio": "350000",
     "answers": ("4", "2", "C", "2", "C", "2", "3", "B", "2", "C", "3", "4", "C", "4", "4", "B", "2", "2")},
    {"id": "arjun", "name": "Arjun", "description": "Single income, two children; prioritising education",
     "occupation": "Operations manager", "age": 42,
     "income": "175000", "expenses": "120000", "liquid": "500000",
     "goal": "Children's education", "goal_type": "education", "target": "5000000",
     "funding": "1800000", "horizon": 8, "portfolio": "1800000",
     "answers": ("3", "4", "B", "4", "B", "3", "3", "B", "3", "B", "2", "3", "C", "4", "3", "B", "3", "3")},
)


def persona_catalogue(db: Session) -> list[dict]:
    instrument = current_instrument(db)
    if instrument.version != "1.0":
        raise DomainError("Demo personas require instrument 1.0; refresh the fixed answer fixtures before use")
    questions = instrument.payload["questions"]
    result = []
    for persona in PERSONAS:
        row = deepcopy(persona)
        fixed = []
        if len(questions) != len(row["answers"]):
            raise DomainError("Demo fixed answer count does not match the assessment instrument")
        answers_by_id = {f"Q{index:03d}": answer for index, answer in enumerate(row.pop("answers"), 1)}
        for question in questions:
            answer = answers_by_id.get(question["id"])
            option = next((opt for opt in question["options"] if opt["id"] == answer), None)
            if option is None:
                raise DomainError("Demo fixed answer is not valid for the assessment instrument")
            fixed.append({"question_id": question["id"], "question": question["text"],
                          "answer_id": answer, "answer": option["text"],
                          "confidence": 75, "response_time_ms": 5000})
        scenario = SCENARIOS[row["id"]]
        row.update(household=scenario["household"], holding_count=len(scenario["positions"])+len(scenario["debt_buckets"]),
                   goal_count=3, fd_count=len(scenario["fds"]), holding_names=[symbol for symbol, _, _ in scenario["positions"]], fixture_version=2)
        row.update(synthetic=True, instrument_version=instrument.version, fixed_answers=fixed)
        result.append(row)
    return result


def launch_persona(db: Session, persona_id: str) -> dict:
    persona = next((p for p in persona_catalogue(db) if p["id"] == persona_id), None)
    if persona is None:
        raise DomainError("Demo persona not found")
    user = identity.create_user(db, f"{persona['name']} (synthetic demo)")
    session = assessments.start_assessment(db, user.id)
    for answer in persona["fixed_answers"]:
        assessments.submit_response(db, session.id, answer["question_id"], answer["answer_id"],
                                    answer["confidence"], answer["response_time_ms"])
    assessments.complete_assessment(db, session.id)
    populate_financial_scenario(db, user.id, persona)
    for field in ("finances_status", "goals_status", "portfolio_status"):
        journey.set_status(db, user.id, field, "provided")
    journey.set_step(db, user.id, "analysis")
    db.flush()
    return {"user": user, "session_id": session.id, "persona": persona}
