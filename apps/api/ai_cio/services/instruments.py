"""Instrument seed and public question payload (no option scores)."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from ai_cio.db.models import Instrument
from ai_cio.psychometrics.instrument import instrument_from_payload
from ai_cio.settings import INSTRUMENT_PATH


class DomainError(ValueError):
    pass


def seed_instrument(db: Session, path: str | Path | None = None) -> Instrument:
    source = Path(path) if path else INSTRUMENT_PATH
    payload = json.loads(source.read_text())
    version = str(payload["version"])
    instrument_from_payload(payload)
    row = db.query(Instrument).filter(Instrument.version == version).one_or_none()
    if row is None:
        row = Instrument(version=version, payload=payload)
        db.add(row)
        db.flush()
        return row
    row.payload = payload
    db.flush()
    return row


def current_instrument(db: Session) -> Instrument:
    row = db.query(Instrument).order_by(Instrument.id.desc()).first()
    if row is None:
        raise DomainError("No instrument seeded. Run: python -m ai_cio.seed")
    return row


def questions_for_client(payload: dict) -> list[dict]:
    """Questions for the UI: option scores are omitted so the client cannot score."""
    questions = []
    for raw in payload.get("questions", []):
        questions.append(
            {
                "id": raw["id"],
                "type": raw["type"],
                "dimension": raw["dimension"],
                "text": raw["text"],
                "options": [{"id": opt["id"], "text": opt["text"]} for opt in raw["options"]],
            }
        )
    return questions


def public_questions(db: Session) -> dict:
    row = current_instrument(db)
    return {
        "instrument_id": row.id,
        "version": row.version,
        "questions": questions_for_client(row.payload),
    }
