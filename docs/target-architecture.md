# Target Architecture — AI-CIO

> Status: **IMPLEMENTED**

```text
apps/web/              Next.js UI
apps/api/
  ai_cio/              FastAPI + domain services + DB
  domain/              CAS parser, portfolio math
  aicio_mcp/           MCP server
packages/              Shared UI, contracts, utils
instruments/           Psychometric instrument
tests/                 pytest
```

Legacy removed: `parv-main/`, Streamlit `frontend/`, root SQLite helpers.
