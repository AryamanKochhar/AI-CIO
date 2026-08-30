# Migration Map — AI-CIO

> Updated after legacy cleanup (August 2026).

| Path | Status | Notes |
|------|--------|-------|
| `apps/web/` | **Active** | Canonical Next.js UI |
| `apps/api/ai_cio/` | **Active** | FastAPI, services, DB models |
| `apps/api/domain/` | **Active** | CAS parser, portfolio analysis |
| `apps/api/aicio_mcp/` | **Active** | MCP stdio server |
| `packages/*` | **Active** | Shared UI, contracts, utils |
| `parv-main/` | **DELETED** | Legacy duplicate app |
| `frontend/` | **DELETED** | Legacy Streamlit UI |
| `database.py` | **DELETED** | Legacy SQLite |
| `config.py` | **DELETED** | Legacy config |
| Root `parser.py`, `analysis.py`, `server.py` | **MOVED** | → `apps/api/domain/`, `apps/api/aicio_mcp/` |
