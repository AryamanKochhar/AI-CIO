# Architecture — AI-CIO

The canonical user journey lives in `apps/web` (Next.js). FastAPI in `apps/api/ai_cio` is the application API. PostgreSQL is the system of record.

## Runtime flow

```text
Browser → apps/web (Next.js) → apps/api/ai_cio/api → apps/api/ai_cio/services → PostgreSQL
MCP (host) → apps/api/ai_cio/services → PostgreSQL
```

One `user_id` spans the full onboarding through Digital Financial Twin review.

## Local development

```bash
make dev-up
```

`make dev-up` pulls standard `python:3.12-slim` and `node:20-alpine` images and mounts the repo — **no custom Docker image build**, avoiding Docker Desktop build-cache I/O failures. Dependencies install at container start (cached via named volumes).

See [development-guide.md](development-guide.md) and [development-architecture.mmd](development-architecture.mmd).

## Database

- **One PostgreSQL container** for local development
- Persistent volume: `postgres_data`
- Test database `ai_cio_test` on the same instance (not a second container)
- SQLite is not used at runtime

## Deprecated

- Streamlit `frontend/` — removed
- `parv-main/` — removed
- Not part of `make dev-up`
