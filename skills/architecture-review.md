# Skill: Architecture Review

## Purpose

Audit the AI-CIO codebase before proposing structural changes. Produce a findings document that maps the current runtime, data flow, databases, duplicate/legacy code, and gaps against the canonical target architecture.

## When to use

- Before adding a new service, database, framework, or major dependency.
- When asked to "refactor", "clean up", or "modernise" the codebase.
- At the start of any milestone or before touching files outside your immediate task.
- When you discover files whose role is unclear (legacy root files, `parv-main/`, etc.).

## Architectural constraints

- One product, one application, one user identity.
- Dependency direction is strict: **UI → API → Domain → DB**.
- Canonical database is **PostgreSQL**; SQLite via `database.py` is legacy only.
- FastAPI is the canonical HTTP layer; Streamlit is the only UI client.
- MCP (`server.py`) is read-only model access, not a second product or dashboard.
- Psychometric scoring is instrument-driven; CAS parsing is document-driven.
- No autonomous trades; missing data stays unknown.

## Files to inspect first

1. `README.md` — product goals, run commands, journey.
2. `docs/current-architecture.md` — canonical vs current state, gaps, debt.
3. `docs/architecture.md`, `docs/data-flow.md`, `docs/mcp-tools.md`, `docs/privacy-and-limitations.md` — if they exist.
4. `ai_cio/db/models.py` — canonical schema and domain boundaries.
5. `ai_cio/api/routes.py` — HTTP surface area.
6. `ai_cio/services/*.py` — domain service responsibilities.
7. `frontend/app.py` and `frontend/client.py` — UI flow and API coupling.
8. `alembic/versions/` — schema history; newest migration tells the current DB shape.
9. Root-level legacy files: `database.py`, `config.py`, `parser.py`, `analysis.py`, `server.py`.
10. `parv-main/` — deprecated duplicate runtime.

## Implementation rules

1. Read, do not rewrite, until findings are written.
2. Produce a short findings list:
   - What is the user asking for?
   - Which canonical layer owns that concern?
   - Which existing files already solve part of the problem?
   - Which legacy/duplicate files could confuse the change?
   - Which gaps in the architecture affect the change?
3. Verify the dependency direction for the proposed change: UI→API→Domain→DB.
4. Flag any request that would add a second database, second identity model, second UI, or autonomous trading capability.
5. Recommend the smallest layer that can absorb the change.
6. Share findings with the user before writing code unless the task is trivial and isolated.

## Testing requirements

- Run `pytest -q` before finishing the review to establish a baseline.
- Note any existing failures that predate your change.
- If the review recommends new tests, add them before or alongside implementation.

## Do NOT

- Begin coding a structural change before producing findings.
- Treat `parv-main/`, `database.py`, or `config.py` as canonical without reading `docs/current-architecture.md`.
- Propose adding a new database, service framework, or UI runtime without explicit justification.
- Use architecture-review findings to justify unrelated refactors.

## Definition of done

- [ ] Findings document exists as a comment, issue note, or temporary `docs/findings-*.md`.
- [ ] Findings reference concrete files and line-level responsibilities.
- [ ] Proposed change is mapped to a single canonical layer.
- [ ] Baseline `pytest -q` result is recorded.
- [ ] User has seen and agreed to the findings before non-trivial code changes begin.
