from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from ai_cio.settings import INSTRUMENT_PATH

RAW_SCORE_MIN = 1.0
RAW_SCORE_MAX = 5.0


class InstrumentError(ValueError):
    """Question bank lookup or validation failed."""


@dataclass(frozen=True)
class Option:
    id: str
    text: str
    score: float


@dataclass(frozen=True)
class Question:
    id: str
    type: str
    dimension: str
    text: str
    options: tuple[Option, ...]

    def option(self, answer_id: str) -> Option:
        for option in self.options:
            if option.id == answer_id:
                return option
        known = ", ".join(option.id for option in self.options)
        raise InstrumentError(
            f"Invalid answer_id {answer_id!r} for question {self.id}. Known: {known}"
        )


@dataclass(frozen=True)
class Instrument:
    version: str
    questions: tuple[Question, ...]

    def question(self, question_id: str) -> Question:
        for item in self.questions:
            if item.id == question_id:
                return item
        raise InstrumentError(f"Missing question definition: {question_id}")

    def questions_for(self, dimension: str) -> tuple[Question, ...]:
        return tuple(q for q in self.questions if q.dimension == dimension)

    def dimensions(self) -> tuple[str, ...]:
        seen: list[str] = []
        for question in self.questions:
            if question.dimension not in seen:
                seen.append(question.dimension)
        return tuple(seen)


def load_instrument(path: str | Path | None = None) -> Instrument:
    source = Path(path) if path else INSTRUMENT_PATH
    payload = json.loads(source.read_text())
    return instrument_from_payload(payload)


def instrument_from_payload(payload: dict[str, Any]) -> Instrument:
    if "version" not in payload or "questions" not in payload:
        raise InstrumentError("Instrument payload must include version and questions")
    questions = []
    for raw in payload["questions"]:
        options = tuple(
            Option(id=str(opt["id"]), text=opt["text"], score=float(opt["score"]))
            for opt in raw["options"]
        )
        if not options:
            raise InstrumentError(f"Question {raw.get('id')} has no options")
        questions.append(
            Question(
                id=raw["id"],
                type=raw["type"],
                dimension=raw["dimension"],
                text=raw["text"],
                options=options,
            )
        )
    return Instrument(version=str(payload["version"]), questions=tuple(questions))


def apply_answer(instrument: Instrument, question_id: str, answer_id: str) -> float:
    """Return the question-bank score for answer_id. Never treat the id as the score."""
    return instrument.question(question_id).option(answer_id).score
