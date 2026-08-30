# Testing Strategy — AI-CIO

## Current setup

- Framework: `pytest` with `pytest.ini`.
- Integration marker: `@pytest.mark.integration` for tests that use the canonical database.
- Integration database: PostgreSQL via Docker (`make db-up` or `make dev-up`). Tests use database `ai_cio_test` on the **same** PostgreSQL instance.
- No SQLite runtime fallback — integration tests fail clearly if PostgreSQL is unavailable.
- Schema contract tests: `tests/test_canonical_schema.py` verifies table existence, `Numeric` money columns, and key columns.
- Golden fixture: `tests/fixtures/psychometric_v1_golden.json` provides hand-checked expected scores for the psychometric instrument.

## How to run

Run everything:

```bash
make test
# or
pytest -q
```

Run only integration tests:

```bash
pytest -m integration -q
```

Run only unit / contract tests:

```bash
pytest -m "not integration" -q
```

## Adding tests per feature

### Auth

- Test `POST /auth/register` creates a user with `email` and `password_hash`.
- Test `POST /auth/login` returns the user when credentials match and rejects bad passwords.
- Test that plaintext passwords are never stored.
- Test email uniqueness.

### Digital Financial Twin

- Test `GET /users/{id}/twin` returns the expected sections and provenance tags.
- Test completeness flags reflect real data.
- Test `ready_for_analysis` is false when any core section is missing.
- Test that no values are fabricated when data is absent.

### Documents

- Test unified upload with `kind=cas_pdf` creates `Document`, `SourcePage`, `Fund`, `Holding`, and `Transaction` rows.
- Test `kind=nsdl_statement` / `cdsl_statement` stores the document with `parser_pending=true` and no holdings.
- Test checksum and `parser_version` are populated.
- Test multiple documents per user are preserved.
- Test cross-user document access is rejected.

## Conventions

- Keep unit tests fast and deterministic.
- Use the existing `client` and `db` fixtures in `tests/conftest.py` for API/integration tests.
- If you add a new money column, add it to the schema contract test.
- If you change the instrument, update the golden fixture and hand-check the math.
