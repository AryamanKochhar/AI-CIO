# Skill: API Development

## Purpose

Add or change FastAPI routes so they remain thin HTTP adapters over the domain layer, with proper user scoping, Pydantic schemas, and `DomainError` handling.

## When to use

- Adding a new endpoint to `ai_cio/api/routes.py`.
- Changing request/response shapes in `ai_cio/api/schemas.py`.
- Adding authentication, authorisation, or user-scoping checks.
- Refactoring route logic into services.

## Architectural constraints

- Routes are thin HTTP adapters. Business logic belongs in `ai_cio/services/`.
- Every mutating endpoint is user-scoped and validates the user exists.
- `DomainError` from services is mapped to `HTTPException` (400 or 404 as appropriate).
- Request/response validation uses Pydantic schemas in `ai_cio/api/schemas.py`.
- DB sessions come from `ai_cio/db/session.py:get_db` via FastAPI `Depends`.
- Do not invent endpoints for features that do not exist yet.

## Files to inspect first

1. `ai_cio/api/routes.py` — existing routes and `_http()` mapping.
2. `ai_cio/api/schemas.py` — Pydantic models.
3. `ai_cio/db/session.py` — `get_db` dependency.
4. `ai_cio/services/*.py` — domain services to call.
5. `ai_cio/services/instruments.py` — `DomainError` definition.
6. `tests/test_runtime_unification.py` or similar API integration tests.

## Implementation rules

1. **Thin routes**: each route should validate input, call a service, commit or rollback, and return a response. Avoid branching business logic.
2. **Use Pydantic schemas**: define request bodies and response models in `ai_cio/api/schemas.py`. Reuse existing schemas where possible.
3. **User-scoped**: routes under `/users/{user_id}/...` must validate the user and pass `user_id` to services.
4. **Map `DomainError` to `HTTPException`**: use the existing `_http()` helper or add route-specific mapping. Rollback on mutating failures.
5. **DB transaction discipline**:
   - Call `db.commit()` after successful mutations.
   - Call `db.rollback()` inside `except DomainError` before raising the HTTP exception.
   - Avoid committing inside domain services unless the service is explicitly designed to manage its own transaction.
6. **No fake future endpoints**: do not add routes for features that are only planned. Add the route when the service exists.
7. **Consistent URL patterns**: follow existing REST-ish conventions (`/users/{user_id}/resources`, `/resources/{id}/actions`).
8. **File uploads**: stream to temporary files and pass paths to domain services; delete temporary files in `finally`.
9. **Auth routes**: keep `/auth/*` thin and delegate to `identity_svc`.
10. **Document uploads**: prefer the unified `/users/{user_id}/documents` endpoint; keep `/users/{user_id}/documents/cas` for backward compatibility.

## Testing requirements

- Add API integration tests using the `client` fixture for new routes.
- Test 400/404 paths by triggering `DomainError` conditions.
- Test user isolation where applicable.
- Run `pytest tests/test_runtime_unification.py -q` and any relevant new test file.
- Run `pytest -q` before finishing.

## Do NOT

- Put business logic, calculations, or DB queries directly in routes.
- Return raw SQLAlchemy objects without serialisation.
- Swallow `DomainError`; always map it to an `HTTPException`.
- Add endpoints for unimplemented features.
- Perform direct DB mutations outside a service call unless the change is trivial and read-only.
- Skip rollback on failure.

## Definition of done

- [ ] New route(s) added to `ai_cio/api/routes.py` with appropriate methods and paths.
- [ ] Schemas added or updated in `ai_cio/api/schemas.py`.
- [ ] Routes call domain services, not raw DB logic.
- [ ] `DomainError` is mapped to `HTTPException` with rollback.
- [ ] User scoping validated for user-owned resources.
- [ ] Integration tests cover success and error paths.
- [ ] `pytest -q` passes.
