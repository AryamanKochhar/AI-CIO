"""Canonical scorer tests. Expected values are hand-checked against instruments/v1.0.json."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_cio.psychometrics.instrument import InstrumentError, apply_answer, load_instrument
from ai_cio.psychometrics.observations import generate_observations
from ai_cio.psychometrics.polarity import DIMENSION_POLARITY
from ai_cio.psychometrics.scoring import AnswerInput, calculate_profile

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "psychometric_v1_golden.json"
SCORE_KEYS = (
    "risk_score",
    "loss_aversion_score",
    "anchoring_score",
    "recency_bias_score",
    "herding_score",
    "overconfidence_score",
    "decision_stability_score",
)


def _instrument():
    return load_instrument(ROOT / "instruments" / "v1.0.json")


def _golden():
    return json.loads(GOLDEN_PATH.read_text())


def _answers(mapping: dict[str, str], confidence: int = 80, response_time_ms: int = 20000):
    return [
        AnswerInput(question_id=qid, answer_id=aid, confidence=confidence, response_time_ms=response_time_ms)
        for qid, aid in mapping.items()
    ]


def _neutral_scores(**overrides: float) -> dict[str, float]:
    scores = {key: 50.0 for key in SCORE_KEYS}
    scores.update(overrides)
    return scores


def test_answer_configured_score_is_used_rather_than_id():
    instrument = _instrument()
    # Q013 A has score 2; treating the letter as A=1 would be wrong.
    assert apply_answer(instrument, "Q013", "A") == 2.0
    # Q003 C has score 4; A=1,B=2,C=3 would yield 3.
    assert apply_answer(instrument, "Q003", "C") == 4.0
    # Q016 B has score 3, not 2.
    assert apply_answer(instrument, "Q016", "B") == 3.0


def test_reverse_scored_question_uses_json_score():
    instrument = _instrument()
    # Q002 id 5 is Strongly Agree (prefer steady returns) with score 1, not 5.
    assert apply_answer(instrument, "Q002", "5") == 1.0
    assert apply_answer(instrument, "Q002", "1") == 5.0
    profile = calculate_profile(
        instrument,
        _answers({**_golden()["answers"], "Q002": "5"}),
    )
    # risk: Q001=5, Q002=1, Q015=5 → mean 3.666… → 66.7
    assert profile["score_applied_by_question"]["Q002"] == 1.0
    assert profile["risk_score"] == 66.7


def test_dimension_with_multiple_questions_aggregates_mean():
    instrument = _instrument()
    answers = dict(_golden()["answers"])
    answers["Q001"] = "1"  # score 1
    answers["Q002"] = "1"  # score 5 (reverse)
    answers["Q015"] = "5"  # score 5
    profile = calculate_profile(instrument, _answers(answers))
    assert profile["score_applied_by_question"]["Q001"] == 1.0
    assert profile["score_applied_by_question"]["Q002"] == 5.0
    assert profile["score_applied_by_question"]["Q015"] == 5.0
    # (1+5+5)/3 = 3.666… → ((3.666…-1)/4)*100 = 66.7
    assert profile["risk_score"] == 66.7


def test_observation_polarity_follows_question_bank():
    high_loss = "\n".join(generate_observations(_neutral_scores(loss_aversion_score=90)))
    low_loss = "\n".join(generate_observations(_neutral_scores(loss_aversion_score=10)))
    assert "lower / more adaptive sensitivity" in high_loss
    assert "greater sensitivity to investment losses" not in high_loss
    assert "greater sensitivity to investment losses" in low_loss
    assert "lower / more adaptive sensitivity" not in low_loss

    high_anchor = "\n".join(generate_observations(_neutral_scores(anchoring_score=90)))
    low_anchor = "\n".join(generate_observations(_neutral_scores(anchoring_score=10)))
    assert "less anchoring" in high_anchor
    assert "greater reliance on prior prices" in low_anchor


def test_all_seven_dimensions_are_within_0_100():
    profile = calculate_profile(_instrument(), _answers(_golden()["answers"]))
    for key in SCORE_KEYS:
        assert 0.0 <= profile[key] <= 100.0


def test_same_answers_produce_identical_profile():
    instrument = _instrument()
    answers = _answers(_golden()["answers"])
    first = calculate_profile(instrument, answers)
    second = calculate_profile(instrument, answers)
    assert first == second


def test_changing_one_answer_changes_only_that_dimension():
    instrument = _instrument()
    base = calculate_profile(instrument, _answers(_golden()["answers"]))
    changed = dict(_golden()["answers"])
    changed["Q001"] = "1"  # risk only; score 1 instead of 5
    updated = calculate_profile(instrument, _answers(changed))
    assert updated["risk_score"] != base["risk_score"]
    for key in SCORE_KEYS:
        if key == "risk_score":
            continue
        assert updated[key] == base[key]
    assert updated["score_applied_by_question"]["Q001"] == 1.0


def test_golden_fixture_matches_hand_calculated_scores():
    golden = _golden()
    profile = calculate_profile(_instrument(), _answers(golden["answers"], golden["confidence"], golden["response_time_ms"]))
    assert profile["instrument_version"] == golden["instrument_version"]
    assert profile["score_applied_by_question"] == golden["expected_score_applied"]
    for key, expected in golden["expected_scores"].items():
        assert profile[key] == expected, f"{key}: {profile[key]} != {expected}"
    assert profile["answer_id_by_question"]["Q002"] == "1"
    assert profile["score_applied_by_question"]["Q002"] == 5.0
    assert "loss_aversion" in profile["polarity"]
    assert profile["polarity"]["loss_aversion"]["higher_means"].startswith("lower")


def test_invalid_answer_id_is_rejected():
    with pytest.raises(InstrumentError, match="Invalid answer_id"):
        apply_answer(_instrument(), "Q001", "Z")
    with pytest.raises(InstrumentError, match="Invalid answer_id"):
        calculate_profile(_instrument(), _answers({**_golden()["answers"], "Q001": "Z"}))


def test_missing_question_definition_is_rejected():
    with pytest.raises(InstrumentError, match="Missing question definition"):
        apply_answer(_instrument(), "Q999", "1")
    extra = _answers(_golden()["answers"]) + [AnswerInput("Q999", "1", 80, 20000)]
    with pytest.raises(InstrumentError, match="Missing question definition"):
        calculate_profile(_instrument(), extra)


def test_polarity_question_ids_match_instrument():
    instrument = _instrument()
    for dimension, spec in DIMENSION_POLARITY.items():
        actual = tuple(q.id for q in instrument.questions_for(dimension))
        assert actual == spec["question_ids"]


def test_canonical_instrument_matches_parv_question_bank():
    canonical = (ROOT / "instruments" / "v1.0.json").read_text()
    parv = (ROOT / "parv-main" / "data" / "questions.json").read_text()
    assert json.loads(canonical) == json.loads(parv)
