"""Deterministic psychometric scoring from the versioned question bank.

Lookup path: question_id → answer_id → option.score → dimension average → 0–100.

This module must not treat answer identifiers as scores. Reverse-scored Likert
items and scenario options are defined only in the instrument JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from ai_cio.psychometrics.instrument import (
    RAW_SCORE_MAX,
    RAW_SCORE_MIN,
    Instrument,
    InstrumentError,
    apply_answer,
)
from ai_cio.psychometrics.observations import generate_observations
from ai_cio.psychometrics.polarity import DIMENSION_POLARITY, polarity_payload

PROFILE_KEYS = {
    "risk_tolerance": "risk_score",
    "loss_aversion": "loss_aversion_score",
    "anchoring": "anchoring_score",
    "recency_bias": "recency_bias_score",
    "herding": "herding_score",
    "overconfidence": "overconfidence_score",
    "decision_stability": "decision_stability_score",
}


@dataclass(frozen=True)
class AnswerInput:
    question_id: str
    answer_id: str
    confidence: int = 0
    response_time_ms: int = 0


@dataclass(frozen=True)
class AppliedResponse:
    question_id: str
    answer_id: str
    score_applied: float
    dimension: str
    confidence: int
    response_time_ms: int


def apply_responses(instrument: Instrument, answers: Iterable[AnswerInput]) -> list[AppliedResponse]:
    applied: list[AppliedResponse] = []
    seen: set[str] = set()
    for answer in answers:
        if answer.question_id in seen:
            raise InstrumentError(f"Duplicate response for {answer.question_id}")
        seen.add(answer.question_id)
        question = instrument.question(answer.question_id)
        score = apply_answer(instrument, answer.question_id, answer.answer_id)
        applied.append(
            AppliedResponse(
                question_id=answer.question_id,
                answer_id=answer.answer_id,
                score_applied=score,
                dimension=question.dimension,
                confidence=answer.confidence,
                response_time_ms=answer.response_time_ms,
            )
        )
    return applied


def normalize_raw_average(raw_average: float) -> float:
    """Map instrument raw mean (1–5) onto the stored 0–100 profile scale."""
    span = RAW_SCORE_MAX - RAW_SCORE_MIN
    normalized = ((raw_average - RAW_SCORE_MIN) / span) * 100.0
    return round(max(0.0, min(100.0, normalized)), 1)


def _dimension_scores(instrument: Instrument, applied: list[AppliedResponse]) -> dict[str, float]:
    by_dimension: dict[str, list[float]] = {name: [] for name in instrument.dimensions()}
    for row in applied:
        by_dimension[row.dimension].append(row.score_applied)
    scores: dict[str, float] = {}
    for dimension in instrument.dimensions():
        values = by_dimension[dimension]
        if not values:
            raise InstrumentError(f"No responses for dimension {dimension}")
        scores[dimension] = normalize_raw_average(sum(values) / len(values))
    return scores


def _average_confidence(applied: list[AppliedResponse]) -> float:
    if not applied:
        return 0.0
    return round(sum(row.confidence for row in applied) / len(applied), 1)


def _average_response_time(applied: list[AppliedResponse]) -> float:
    if not applied:
        return 0.0
    return round(sum(row.response_time_ms for row in applied) / len(applied), 1)


def _profile_confidence(applied: list[AppliedResponse], avg_confidence: float) -> float:
    if not applied:
        return 0.0
    confidence_signal = max(0.0, min(100.0, avg_confidence))
    timing_scores = []
    confidence_values = [row.confidence for row in applied]
    for row in applied:
        seconds = max(row.response_time_ms, 0) / 1000
        timing_scores.append(100 * math.exp(-((seconds - 20) / 20) ** 2))
    timing_signal = sum(timing_scores) / len(timing_scores)
    mean_confidence = sum(confidence_values) / len(confidence_values)
    variance = sum((value - mean_confidence) ** 2 for value in confidence_values) / len(confidence_values)
    consistency_signal = max(0.0, 100.0 - math.sqrt(variance))
    reliability = confidence_signal * 0.55 + timing_signal * 0.25 + consistency_signal * 0.20
    return round(max(0.0, min(100.0, reliability)), 1)


def calculate_profile(instrument: Instrument, answers: Iterable[AnswerInput]) -> dict:
    answer_list = list(answers)
    if not answer_list:
        raise InstrumentError("No responses provided")
    applied = apply_responses(instrument, answer_list)
    dimension_scores = _dimension_scores(instrument, applied)
    avg_confidence = _average_confidence(applied)
    avg_time = _average_response_time(applied)
    profile = {
        "instrument_version": instrument.version,
        "risk_score": dimension_scores["risk_tolerance"],
        "loss_aversion_score": dimension_scores["loss_aversion"],
        "anchoring_score": dimension_scores["anchoring"],
        "recency_bias_score": dimension_scores["recency_bias"],
        "herding_score": dimension_scores["herding"],
        "overconfidence_score": dimension_scores["overconfidence"],
        "decision_stability_score": dimension_scores["decision_stability"],
        "average_confidence": avg_confidence,
        "average_response_time_ms": avg_time,
        "profile_confidence": _profile_confidence(applied, avg_confidence),
        "score_applied_by_question": {row.question_id: row.score_applied for row in applied},
        "answer_id_by_question": {row.question_id: row.answer_id for row in applied},
        "polarity": polarity_payload(),
    }
    profile["observations"] = generate_observations(
        {key: profile[key] for key in PROFILE_KEYS.values()}
    )
    return profile


__all__ = [
    "AnswerInput",
    "AppliedResponse",
    "DIMENSION_POLARITY",
    "apply_answer",
    "apply_responses",
    "calculate_profile",
    "generate_observations",
    "normalize_raw_average",
]
