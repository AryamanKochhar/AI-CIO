# AI-CIO

One product, one application, one user identity.

AI-CIO is a human-in-the-loop personal financial decision-support system. It walks a person through psychometric onboarding, finances, goals, and document upload inside a single UI, then assembles a Digital Financial Twin for human review.

## Architecture

```text
apps/web (Next.js) → apps/api (FastAPI) → PostgreSQL
apps/api/aicio_mcp → same domain layer → PostgreSQL
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pnpm install
cp .env.example .env

docker compose up -d
alembic upgrade head

# Terminal 1 — API
pnpm dev:api

# Terminal 2 — Web
pnpm dev:web
```

- Web: http://localhost:3000
- API: http://127.0.0.1:8000

## Repository structure

```text
apps/
  web/              Next.js UI (canonical)
  api/
    ai_cio/         FastAPI + domain services + DB models
    domain/         CAS parser & portfolio analysis
    aicio_mcp/      MCP server
packages/
  ui/, contracts/, utils/, config-*/
instruments/        Psychometric instrument (v1.0.json)
tests/              Backend pytest suite
docs/               Architecture documentation
```

## Tests

```bash
pytest -q
pnpm typecheck
pnpm build
```

## MCP

```bash
pnpm mcp
```

## Documentation

- [Current architecture](docs/current-architecture.md)
- [Migration map](docs/migration-map.md)
- [Development guide](docs/development-guide.md)
