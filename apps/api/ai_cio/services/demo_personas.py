"""Transparent synthetic fixtures, scored by the normal assessment workflow.

Every launch creates an isolated user. No real identity, live quote, or return
history is implied by these examples. The fixed answers target instrument 1.0.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ai_cio.db.models import Document, Fund, Holding
from ai_cio.services import assessments, finances, goals, identity, journey
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
    finances.replace_finances(db, user.id, income=persona["income"], expenses=persona["expenses"],
                              liquid=persona["liquid"], liabilities=[])
    goals.create_goal(db, user.id, {"name": persona["goal"], "goal_type": persona["goal_type"],
                                  "target_amount": persona["target"], "current_funding": persona["funding"],
                                  "horizon_years": persona["horizon"], "priority": "high",
                                  "notes": "Synthetic demo assumption; not a real client's goal."})
    document = Document(user_id=user.id, kind="demo_portfolio", filename="SYNTHETIC-DEMO-portfolio.json",
                        status="extracted", validation_status="valid", parser_version="demo-fixture-1",
                        metadata_json={"synthetic": True, "persona": persona_id},
                        warning_json=["Illustrative category holdings. No market quote or transaction history."])
    db.add(document)
    db.flush()
    for label, weight, asset_class in (("Broad equity example", "0.5", "equity"),
                                       ("Debt fund example", "0.3", "debt"),
                                       ("Liquid fund example", "0.2", "debt")):
        fund = Fund(user_id=user.id, document_id=document.id, amc="SYNTHETIC EXAMPLE",
                    folio="DEMO", scheme_name=label)
        db.add(fund)
        db.flush()
        db.add(Holding(user_id=user.id, document_id=document.id, fund_id=fund.id,
                       valuation=Decimal(persona["portfolio"]) * Decimal(weight),
                       valuation_date=date.today().isoformat(), asset_class=asset_class, source_page=1))
    for field in ("finances_status", "goals_status", "portfolio_status"):
        journey.set_status(db, user.id, field, "provided")
    journey.set_step(db, user.id, "analysis")
    db.flush()
    return {"user": user, "session_id": session.id, "persona": persona}
