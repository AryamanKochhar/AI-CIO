# Skill: Domain Development

## Purpose

Add or change business logic inside the AI-CIO domain layer (`ai_cio/services/*.py`) while keeping services pure, user-scoped, and honest about unknowns.

## When to use

- Adding a new domain service or modifying an existing one.
- Implementing validation rules, calculations, or orchestration.
- Moving logic out of the API layer or UI into the domain.
- Adding lifecycle or state-machine behaviour for users, journeys, assessments, finances, goals, portfolio, review, or twin.

## Architectural constraints

- Domain services sit between API and DB. The dependency direction is **API → Domain → DB**.
- Services import and call models from `ai_cio/db/models.py`; they do not perform HTTP calls or render UI.
- Validation errors are raised as `DomainError` (imported from `ai_cio/services/instruments.py`).
- Missing data is **unknown**, not fabricated.
- Every user-owned operation is scoped to a `user_id` and validated with `get_user()` or equivalent.
- Services return plain data structures or ORM objects; serialization belongs in the service or the API schema, not in templates.

## Files to inspect first

1. `ai_cio/services/*.py` — existing service responsibilities and conventions.
2. `ai_cio/db/models.py` — entities and relationships.
3. `ai_cio/api/routes.py` — how services are invoked by HTTP.
4. `ai_cio/api/schemas.py` — Pydantic request/response shapes.
5. `ai_cio/services/instruments.py` — location of `DomainError`.
6. `tests/test_*.py` — relevant service tests.

## Implementation rules

1. **One concern per service**: match the existing module split (identity, instruments, assessments, finances, goals, journey, portfolio, review, twin, documents).
2. **Raise `DomainError` for invalid input or state**, not generic exceptions. Keep messages actionable.
3. **No HTTP in domain**: services must not import FastAPI, requests, or Streamlit.
4. **No fabricated defaults**:
   - If the user did not provide a value, return `None` or `"unknown"`.
   - Do not invent ₹1,00,000 example plans, placeholder incomes, or dummy goals.
5. **Missing = unknown**: explicitly model "unknown" status in returned payloads and, where appropriate, in the database.
6. **User scoping**: begin mutating operations by validating the user exists and that the resource belongs to them.
7. **DB sessions**: accept `sqlalchemy.orm.Session` as the first argument; do not create engines or sessions inside services.
8. **Idempotency**: prefer upserts or replace semantics that make repeated calls safe, unless the lifecycle explicitly forbids it.
9. **Keep functions small and testable**: pure helpers can live in the same module or in a `ai_cio/<domain>/` sub-package.
10. **Document non-obvious tradeoffs** with short comments explaining why a rule exists.

## Testing requirements

- Add unit tests for pure helpers and validation rules.
- Add integration tests using the `db` fixture for service-level persistence and user isolation.
- Run `pytest tests/test_<area>.py -q` for the affected domain.
- Run `pytest -q` before finishing.

## Do NOT

- Put HTTP or UI code in domain services.
- Use `print` for errors; raise `DomainError`.
- Fabricate values when data is missing.
- Bypass `get_user()` validation.
- Return Streamlit widgets or FastAPI dependencies from services.
- Import from `frontend/` or `ai_cio/api/` inside domain services.

## Definition of done

- [ ] New or changed logic lives in the correct `ai_cio/services/*.py` module.
- [ ] All validation and state errors raise `DomainError`.
- [ ] Functions accept `Session` and are user-scoped.
- [ ] No HTTP, UI, or framework code leaked into the domain.
- [ ] Missing values are represented as unknown/null, not fabricated.
- [ ] Tests cover validation, success, and user-isolation paths.
- [ ] `pytest -q` passes.
