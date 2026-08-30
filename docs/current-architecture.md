# Current Architecture — AI-CIO

> Status: **IMPLEMENTED** (August 2026)

## Summary

Modular monorepo with Next.js UI, Python API under `apps/api/`, and PostgreSQL.

```text
apps/web → apps/api/ai_cio/api → apps/api/ai_cio/services → PostgreSQL
apps/api/aicio_mcp → same services → PostgreSQL
```

## Entry points

| Component | Command |
|-----------|---------|
| Web UI | `pnpm dev:web` |
| API | `pnpm dev:api` |
| MCP | `pnpm mcp` |
| CLI CAS ingest | `python scripts/ingest.py data/cas.pdf --user-id 1` |

## Removed legacy (August 2026)

- `parv-main/` — old duplicate psychometric app
- `frontend/` — Streamlit UI (replaced by `apps/web`)
- `database.py`, `config.py` — SQLite legacy helpers

## Test status

53+ pytest tests (SQLite legacy test removed with `database.py`).
