# Current Architecture — AI-CIO

> Status: **IMPLEMENTED** after monorepo restructure (August 2026).

## Executive summary

AI-CIO is a modular monorepo with:

- **Canonical UI**: Next.js (`apps/web`)
- **Canonical API**: FastAPI (`ai_cio/api`)
- **Canonical database**: PostgreSQL via SQLAlchemy + Alembic
- **Domain layer**: `ai_cio/services/` + root `parser.py` / `analysis.py`
- **MCP**: `server.py` (stdio, read-only domain access)

Streamlit (`frontend/`) and Parv (`parv-main/`) are **deprecated** but retained temporarily.

## Runtime entry points

| Entry point | Command | Purpose |
|-------------|---------|---------|
| Web UI | `pnpm dev:web` | Canonical Next.js application |
| API | `python -m ai_cio.api` | FastAPI server |
| MCP | `python server.py` | Model context protocol |
| Streamlit (legacy) | `streamlit run frontend/app.py` | Deprecated UI |
| CLI ingest | `python scripts/ingest.py data/cas.pdf --user-id N` | CAS CLI ingest |

## Data flow

```text
User → Next.js (apps/web) → FastAPI → Domain services → PostgreSQL
MCP → Domain services → PostgreSQL
```

## Implemented capabilities

| Capability | Status |
|------------|--------|
| MVP auth (register/login, PBKDF2) | ✅ |
| Psychometric assessment (server-side scoring) | ✅ |
| Financial onboarding | ✅ |
| Goals CRUD | ✅ |
| Unified document upload (CAS + NSDL/CDSL/other) | ✅ |
| CAS parsing | ✅ |
| NSDL/CDSL storage (parser pending) | ✅ |
| Portfolio review | ✅ |
| Digital Financial Twin assembly | ✅ |
| User isolation tests | ✅ |
| MCP read tools | ✅ |

## Test status

54 pytest tests passing (integration + unit).

## Deprecated / legacy

| Path | Status |
|------|--------|
| `parv-main/` | Deprecated redirect |
| `frontend/` (Streamlit) | Deprecated UI |
| `database.py` | Legacy SQLite only |
| `config.py` | Superseded by `ai_cio/settings.py` |

See [migration-map.md](migration-map.md) for full mapping.
