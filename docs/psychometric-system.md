# Psychometric System — AI-CIO

> Status: **IMPLEMENTED**. Server-side scoring only; the client never scores.

## Overview

The psychometric system is a versioned, instrument-driven questionnaire. It produces a behavioural profile used by the Digital Financial Twin and review output.

- Instrument file: `instruments/v1.0.json`
- Loader/parser: `ai_cio/psychometrics/instrument.py`
- Scoring: `ai_cio/psychometrics/scoring.py`
- Polarity definitions: `ai_cio/psychometrics/polarity.py`
- Observations: `ai_cio/psychometrics/observations.py`
- Seed/public payload: `ai_cio/services/instruments.py`

## Instrument

The canonical instrument is version `1.0`.

- **18 questions** across **7 dimensions**.
- Question types are `likert` and `scenario`.
- Each option has an explicit `id` (what the UI sends) and a `score` (used only server-side).
- Reverse-scored items are handled entirely in the JSON; scoring code never treats answer ids as scores.

### Dimensions

| Dimension | Profile key | Question ids | Higher score means |
|-----------|-------------|--------------|--------------------|
| Risk tolerance | `risk_score` | Q001, Q002, Q015 | Greater willingness to accept investment risk |
| Loss aversion | `loss_aversion_score` | Q003, Q004, Q016 | Lower / more adaptive sensitivity to losses |
| Anchoring | `anchoring_score` | Q005, Q006, Q018 | Less anchoring to prior prices |
| Recency bias | `recency_bias_score` | Q007, Q008 | Less overweighting of recent performance |
| Herding | `herding_score` | Q009, Q010, Q017 | More independent decision-making |
| Overconfidence | `overconfidence_score` | Q011, Q012 | More calibrated view of personal skill |
| Decision stability | `decision_stability_score` | Q013, Q014 | Greater decision stability / maintaining conviction |

## Scoring math

1. For each response, look up `question_id` → `answer_id` → `option.score`.
2. Build per-dimension raw score lists.
3. Compute the raw mean for each dimension (instrument raw range is 1–5).
4. Normalize to a 0–100 scale:

```text
normalized = ((raw_mean - 1) / (5 - 1)) * 100
```

5. Clamp to `[0, 100]` and round to one decimal place.

## Stored response

`assessment_responses` stores both `answer_id` and `score_applied` so the audit trail is independent of the scoring code.

## Profile fields

`behavioral_profiles` stores one row per completed session with:

- One score column per dimension (0–100).
- `average_confidence`: mean user-reported confidence.
- `average_response_time_ms`: mean response time.
- `profile_confidence`: composite reliability estimate combining confidence, response timing, and inter-response consistency.
- `polarity`: JSON payload describing what higher/lower scores mean for each dimension.

## Observations

`ai_cio/psychometrics/observations.py` generates plain-language observations from the stored scores using the polarity definitions. The thresholds are:

- `HIGH` ≥ 70
- `LOW` < 40

For risk tolerance, all three bands produce text; for bias-labelled dimensions, only high/low produce a statement (moderate scores are silent).

## API flow

1. `GET /instruments/current/questions` returns questions without option scores.
2. `POST /assessments/start` creates an `AssessmentSession`.
3. `POST /assessments/{id}/responses` records `answer_id` and server-computed `score_applied`.
4. `POST /assessments/{id}/complete` runs `calculate_profile` and persists a `BehavioralProfile`.
5. `GET /assessments/{id}/observations` returns plain-language observations.

## Planned changes

None beyond maintenance and possible new instrument versions. No client-side scoring, no adaptive testing, and no external psychometric services are implemented or planned for the MVP.
