# Skill: Testing

## Purpose

Write and run tests for AI-CIO consistently, distinguishing unit, integration, and contract tests, and using the test database infrastructure already in place.

## When to use

- Before finishing any code change.
- When adding a new feature, service, route, parser, or model.
- When verifying a bug fix or refactoring.
- When setting up a new test file or fixture.

## Architectural constraints

- Test runner: **pytest**.
- Integration tests that touch the database use a Postgres container when Docker is available; otherwise they fall back to SQLite in-memory.
- DB-touching tests rely on the `db` and `client` fixtures in `tests/conftest.py`.
- Schema contract tests in `tests/test_canonical_schema.py` assert canonical invariants.
- Psychometric golden fixture tests in `tests/test_psychometric_scoring.py` must always pass.
- Parser tests use fixture PDFs in `tests/fixtures/`.

## Files to inspect first

1. `tests/conftest.py` — fixtures, DB setup, Docker/Postgres fallback.
2. `tests/test_canonical_schema.py` — schema contract tests.
3. `tests/test_psychometric_scoring.py` — golden fixture tests.
4. `tests/test_parser.py` — parser unit tests.
5. `tests/test_runtime_unification.py` — API/integration tests.
6. `tests/fixtures/` — PDFs and golden JSON.

## Implementation rules

1. **Run `pytest -q` before finishing any change.** This is the minimum acceptance criterion.
2. **Mark integration tests**: use `@pytest.mark.integration` for tests that require the database or external services. The project may rely on fixture autostart behaviour; follow existing conventions.
3. **Use the `db` fixture** for service-level integration tests; use the `client` fixture for API tests.
4. **Keep tests deterministic**: avoid tests that depend on wall-clock time, randomness, or external network unless explicitly mocked.
5. **Golden fixtures**: for psychometric scoring and parser output, store expected outputs in `tests/fixtures/` and compare them exactly. Update the golden file only when the expected behaviour intentionally changes.
6. **Contract tests**: when adding a new table or column, add assertions about:
   - Non-nullable `user_id` on user-owned tables.
   - `Numeric` type for money columns.
   - Timezone-aware datetime columns.
   - Check constraints for enum-like columns.
7. **User isolation**: integration tests should verify that one user's data is not visible or mutable by another user.
8. **Mock external systems**: do not call real email providers, broker APIs, or market data services in tests.
9. **Test naming**: use descriptive names that explain the behaviour under test.
10. **Avoid over-mocking domain logic**: unit-test pure helpers directly; integration-test service orchestration against the DB.

## Testing requirements

- `pytest -q` must pass before a task is considered done.
- New features must include tests that would fail if the feature were removed.
- Bug fixes must include a regression test.
- Psychometric and parser golden fixture tests must remain green.
- Schema contract tests must remain green after any model change.

## Do NOT

- Skip running tests because the change "seems safe".
- Write tests that depend on a local Postgres instance if they cannot fall back to SQLite via the existing fixtures.
- Mutate golden fixtures to match new output without verifying the change is correct.
- Add long-running tests without a clear reason or timeout.
- Leave failing tests in the suite unless they are explicitly marked as expected-fail with a documented reason.

## Definition of done

- [ ] Tests added or updated for the changed code.
- [ ] `pytest -q` passes locally.
- [ ] New tests fail if the new behaviour is reverted.
- [ ] Golden fixtures and contract tests still pass.
- [ ] No test depends on unstated external state.
