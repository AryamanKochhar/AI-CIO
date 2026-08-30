# Skill: Database Change

## Purpose

Safely evolve the PostgreSQL schema for AI-CIO by changing `ai_cio/db/models.py` and adding a forward-only Alembic migration. Preserve data integrity, money precision, user scoping, and timezone awareness.

## When to use

- Adding a new table, column, index, check constraint, or enum.
- Changing column types, nullability, or defaults.
- Adding user-owned entities or linking existing ones to `users.id`.
- Refactoring models to support new domain requirements.

## Architectural constraints

- PostgreSQL is the canonical database. SQLite via `database.py` is legacy.
- SQLAlchemy 2.0 ORM models live in `ai_cio/db/models.py`.
- Alembic migrations live in `alembic/versions/` and are the source of truth for schema changes.
- Money is always `Numeric`, never `Float`.
- Datetimes are timezone-aware (`DateTime(timezone=True)`), defaulting to UTC.
- Every user-owned row carries `user_id` with a foreign key to `users.id` and an index.
- Use `JSONBCompat` (`JSON().with_variant(JSONB(), "postgresql")`) for JSON columns unless there is a specific reason not to.

## Files to inspect first

1. `ai_cio/db/models.py` — current model definitions and conventions.
2. `alembic/versions/` — newest migration; verify `down_revision` chain.
3. `alembic/env.py` — metadata and migration context.
4. `tests/test_canonical_schema.py` — schema contract tests.
5. `tests/conftest.py` — test database setup and fixtures.

## Implementation rules

1. **Edit models first**: update `ai_cio/db/models.py` before writing the migration. Keep style consistent with existing models.
2. **New migration only**: generate a new Alembic revision with `alembic revision --autogenerate -m "..."` or hand-write it. **Never edit committed migrations.**
3. **Forward-only**: design migrations to run against production-like data. Avoid destructive renames without a transition plan.
4. **Money columns**: use `Numeric` for any monetary value (e.g., `target_amount`, `balance`, `valuation`). Never `Float` for money.
5. **Timezone**: declare all `DateTime` columns as `DateTime(timezone=True)` and use `datetime.now(timezone.utc)` or the existing `_utcnow` helper.
6. **User scoping**: every entity that belongs to a user must have:
   - `user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)`
   - Queries scoped to `user_id` in the owning service.
7. **Check constraints**: add `CheckConstraint` in the model for enum-like columns and mirror it in the migration.
8. **Defaults**: prefer server defaults only where they are safe and explicit; avoid implicit magic values.
9. **JSON columns**: use `JSONBCompat` for compatibility across Postgres and SQLite test fallback.
10. **Run the migration locally**: `alembic upgrade head` and `alembic downgrade -1` to verify.

## Testing requirements

- Run schema contract tests: `pytest tests/test_canonical_schema.py -q`.
- Run the full suite: `pytest -q` before finishing.
- If adding a new user-owned table, add a test that verifies `user_id` is non-nullable and indexed.
- If adding monetary columns, add a test that asserts the column type is `Numeric`.
- Test the migration up/down against the local Postgres container if available.

## Do NOT

- Edit old Alembic revisions.
- Use `Float` for money or financial quantities.
- Add nullable `user_id` columns on user-owned rows.
- Create raw SQL tables outside the ORM + migration pair.
- Add migrations that depend on application code beyond standard SQLAlchemy/Alembic.
- Assume SQLite-only behavior in production; validate on Postgres.

## Definition of done

- [ ] `ai_cio/db/models.py` updated and consistent with existing style.
- [ ] New Alembic revision created with correct `revision` / `down_revision`.
- [ ] Migration applies cleanly with `alembic upgrade head`.
- [ ] Migration rolls back cleanly one step with `alembic downgrade -1` (if rollback is safe).
- [ ] Schema contract tests pass.
- [ ] Full `pytest -q` passes.
- [ ] Any new money columns are `Numeric`; any new datetime columns are timezone-aware; any new user-owned rows have `user_id`.
