# AI-CIO API

Canonical Python backend for AI-CIO.

## Structure

```text
apps/api/
├── ai_cio/           # FastAPI app, domain services, database models
│   ├── api/
│   ├── db/
│   ├── psychometrics/
│   └── services/
├── domain/
│   ├── parser.py     # CAS PDF parser
│   └── analysis.py   # Portfolio calculations
└── aicio_mcp/
    └── server.py     # MCP stdio server
```

## Run

From the repository root (with venv active):

```bash
PYTHONPATH=apps/api python -m ai_cio.api
PYTHONPATH=apps/api python -m aicio_mcp
```

Or use root scripts:

```bash
pnpm dev:api
pnpm mcp
```

## Dependency direction

```text
FastAPI routes → ai_cio/services → ai_cio/db → PostgreSQL
MCP → ai_cio/services → PostgreSQL
domain/parser.py → used by portfolio service (pure functions)
```
