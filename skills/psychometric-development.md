# Skill: Psychometric Development

## Purpose

Change the psychometric instrument, scoring, polarity, or observations while preserving instrument-driven, server-side scoring and explicit polarity rules.

## When to use

- Modifying `instruments/v1.0.json` or adding a new instrument version.
- Changing scoring logic in `ai_cio/psychometrics/scoring.py`.
- Adding dimensions, questions, options, or answer weights.
- Updating observations or polarity labels in `ai_cio/psychometrics/polarity.py`.
- Fixing how `AssessmentResponse.score_applied` is recorded.

## Architectural constraints

- The instrument JSON in `instruments/v1.0.json` is the source of truth for questions, options, and scores.
- `Instrument.payload` stores the seeded instrument in PostgreSQL.
- The UI never scores; scoring happens server-side in `ai_cio/psychometrics/scoring.py`.
- Option scores are looked up by `answer_id` from the instrument JSON, never reinterpreted by the UI or API.
- Polarity is explicit: higher scores on bias-labelled dimensions mean more adaptive / less biased behaviour.
- Instruments are versioned. A change to the instrument should generally be a new version, not an in-place mutation of a live version.

## Files to inspect first

1. `instruments/v1.0.json` — current canonical instrument.
2. `ai_cio/psychometrics/scoring.py` — score computation.
3. `ai_cio/psychometrics/polarity.py` — dimension polarity and observations.
4. `ai_cio/psychometrics/observations.py` — if present, plain-language output.
5. `ai_cio/services/instruments.py` — seeding and public payload filtering.
6. `ai_cio/services/assessments.py` — session lifecycle and scoring orchestration.
7. `ai_cio/db/models.py` — `Instrument`, `AssessmentSession`, `AssessmentResponse`, `BehavioralProfile`.
8. `tests/test_psychometric_scoring.py` — golden fixture tests.
9. `tests/fixtures/psychometric_v1_golden.json` — expected scores for a known response set.

## Implementation rules

1. **Version instruments**: when changing the instrument, create a new JSON file (e.g., `instruments/v1.1.json`) and update the seed to use it. Do not silently mutate a version already in use.
2. **Server-side scoring only**: the public questions endpoint strips scores. The scoring function reads the full instrument payload from the DB.
3. **Answer lookup only from instrument JSON**: `score_applied` must come from `answer_id → option score` in the instrument. Never hard-code answer weights in the API or UI.
4. **Never reinterpret polarity**: if a dimension label changes, update `DIMENSION_POLARITY` explicitly and verify the golden fixture still matches the intended meaning.
5. **Persist provenance**: store `instrument_id`, `session_id`, and `answer_id` so scores can be recomputed or audited.
6. **Polarity output**: `BehavioralProfile.polarity` records the explicit polarity map used at scoring time.
7. **Confidence and timing**: average confidence and response time are computed and stored; do not fabricate them.
8. **Observation language**: observations must be plain-language and derived from scored dimensions and polarity, not from ad hoc rules.

## Testing requirements

- Golden fixture tests **must** pass: `pytest tests/test_psychometric_scoring.py -q`.
- After any instrument change, update or add a golden fixture for the new version and ensure old-version fixtures still pass if supported.
- Add tests that verify the public questions endpoint never exposes option scores.
- Add tests that verify answer-id → score lookup matches the instrument JSON.
- Run `pytest -q` before finishing.

## Do NOT

- Change the meaning of a dimension's polarity without updating the instrument version and golden fixtures.
- Let the UI or browser compute scores.
- Hard-code scores outside the instrument JSON.
- Mutate `instruments/v1.0.json` in place while sessions reference it.
- Fabricate confidence or response-time values.
- Return raw option scores from the public questions endpoint.

## Definition of done

- [ ] Instrument changes are versioned; new version file or seed constant updated.
- [ ] Scoring uses `answer_id` lookup from the instrument payload only.
- [ ] Polarity map is explicit and consistent with the new instrument.
- [ ] Golden fixture tests pass.
- [ ] Public questions endpoint does not leak option scores.
- [ ] Tests cover score lookup, polarity, and observations.
- [ ] `pytest -q` passes.
