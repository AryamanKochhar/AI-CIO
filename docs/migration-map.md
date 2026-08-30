# Migration Map — AI-CIO Monorepo Restructure

> Status: living document updated during the August 2026 restructure.

| Current file / path | Target location | Action | Dependencies | Status | Reason |
|---------------------|-----------------|--------|--------------|--------|--------|
| `ai_cio/` | `ai_cio/` (root) | **KEEP** | Alembic, pytest, MCP | Active | Canonical Python domain package; moving would break Alembic imports without benefit |
| `apps/api/` | `apps/api/` | **NEW** | README only | Active | Monorepo API entry documentation |
| `apps/web/` | `apps/web/` | **NEW** | FastAPI | Active | Canonical Next.js UI replacing Streamlit |
| `frontend/app.py` | — | **DEPRECATE** | FastAPI | Temporary | Streamlit UI superseded by `apps/web`; kept for parity verification |
| `frontend/client.py` | — | **DEPRECATE** | FastAPI | Temporary | HTTP client for Streamlit only |
| `parv-main/` | — | **DEPRECATE** | None | Legacy | Old Parv app; redirect only |
| `database.py` | — | **DEPRECATE** | SQLite tests | Temporary | Legacy SQLite helper; used by `test_database.py` and `--sqlite` ingest |
| `config.py` | `ai_cio/settings.py` | **DEPRECATE** | Legacy scripts | Temporary | Superseded by `ai_cio/settings.py` |
| `parser.py` | `parser.py` (root) | **KEEP** | portfolio, MCP, tests | Active | Working CAS parser; domain utility |
| `analysis.py` | `analysis.py` (root) | **KEEP** | portfolio, MCP, twin | Active | Portfolio calculations |
| `server.py` | `server.py` (root) | **KEEP** | ai_cio services | Active | MCP stdio entry; calls same domain layer |
| `instruments/v1.0.json` | `instruments/v1.0.json` | **KEEP** | psychometrics | Active | Canonical instrument source of truth |
| `packages/ui/` | `packages/ui/` | **NEW** | React | Active | Shared design system |
| `packages/contracts/` | `packages/contracts/` | **NEW** | TypeScript | Active | Frontend/backend type contracts |
| `packages/utils/` | `packages/utils/` | **NEW** | — | Active | Formatting helpers |
| `tests/` | `tests/` | **KEEP** | pytest | Active | Backend test suite (54 tests) |

## Deletion policy

Nothing is deleted until:

1. Replacement exists and is verified
2. Imports migrated
3. Tests pass
4. No remaining references

## Next cleanup phase (PLANNED)

- Remove `parv-main/` after one release cycle with no references
- Remove Streamlit `frontend/` after Next.js parity sign-off
- Move `parser.py` / `analysis.py` into `ai_cio/domain/` when import churn is acceptable
- Move MCP `server.py` to `ai_cio/mcp/server.py`
