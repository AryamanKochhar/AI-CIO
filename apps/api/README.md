# AI-CIO API

Canonical Python backend for AI-CIO.

## Run

From the repository root:

```bash
source .venv/bin/activate
python -m ai_cio.api
```

## Structure

The domain package lives at `ai_cio/` (repository root). This directory documents the API entry point for the monorepo.

```
ai_cio/
├── api/          # FastAPI routes and schemas
├── db/           # SQLAlchemy models and sessions
├── psychometrics/# Instrument scoring
└── services/     # Domain services

parser.py         # CAS PDF parser (domain utility)
analysis.py       # Portfolio calculations (domain utility)
server.py         # MCP stdio server
```

Dependency direction: `api → services → db`. MCP and CLI scripts call the same services.
