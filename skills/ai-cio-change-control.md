# Skill: AI-CIO Change Control

## Purpose

Control non-trivial changes to AI-CIO so the architecture stays unified, intentional, and well-tested. Every significant change must be inspected, justified, documented, and validated before it is considered done.

## When to use

- Before adding new architectural layers, databases, services, or frameworks.
- Before introducing new runtime entry points, UI surfaces, or external integrations.
- Before any change that could duplicate or bypass existing functionality.
- At the start of milestone work, refactors, or feature additions that touch multiple layers.

## Architectural constraints

> Do not introduce new architectural layers, databases, services or frameworks without first checking the existing architecture and explaining why the change is necessary.

- One product, one application, one user identity.
- Dependency direction: **UI → API → Domain → DB**.
- PostgreSQL is the canonical database.
- Reuse existing services, models, and utilities before creating new ones.
- Every change must be testable and must pass the full test suite.

## Files to inspect first

1. `docs/current-architecture.md` — current state, gaps, and safe-to-move notes.
2. `README.md` — product goals and canonical commands.
3. `ai_cio/db/models.py` — canonical schema.
4. `ai_cio/services/*.py` — existing domain capabilities.
5. `ai_cio/api/routes.py` — existing HTTP surface.
6. `frontend/app.py` and `frontend/client.py` — UI surface.
7. `alembic/versions/` — schema history.
8. `tests/` — existing coverage and fixtures.

## Implementation rules

Follow the 7-step change control process for any significant change:

1. **Inspect current** — read the architecture docs, models, services, routes, and tests. Understand the canonical data flow and the single-user identity model.
2. **Identify existing equivalent** — search for existing code that already solves the problem or a closely related problem. Prefer reuse over invention.
3. **Reuse** — extend an existing service, model, route, or UI screen before adding a new one. Keep the dependency direction intact.
4. **Justify** — if no equivalent exists and a new layer/service/framework is required, write a short justification covering:
   - What problem it solves.
   - Why existing code cannot solve it.
   - What alternatives were considered.
   - What risks it introduces.
5. **Document** — update `docs/current-architecture.md` or a temporary `docs/findings-*.md` to reflect the change. If the change affects developers or operators, update `README.md` or add a note.
6. **Test** — add unit, integration, contract, or fixture tests for the change. Run targeted tests first, then the full suite.
7. **Run full suite** — run `pytest -q` and ensure it passes before finishing. If tests fail, fix them or explicitly document why they are out of scope.

## Testing requirements

- Add tests for new behaviour.
- Run targeted tests for the affected layer(s).
- Run `pytest -q` as the final gate.
- Do not consider a change complete while the full suite is failing because of it.

## Do NOT

- Introduce new layers, databases, services, or frameworks without justification.
- Bypass the 7-step process for non-trivial changes.
- Duplicate functionality already present in canonical code.
- Treat legacy files (`database.py`, `config.py`, `parv-main/`) as justification for new canonical code.
- Merge or finish a change without running the full test suite.

## Definition of done

- [ ] Current architecture inspected and understood.
- [ ] Existing equivalent identified (or confirmed absent).
- [ ] Existing code reused where possible.
- [ ] Justification written for any new layer, database, service, or framework.
- [ ] Documentation updated (`docs/current-architecture.md`, `README.md`, or `docs/findings-*.md`).
- [ ] Tests added and targeted test run passes.
- [ ] Full `pytest -q` passes.
