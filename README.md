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
git clone <repo-url>
cd AI-CIO
make install
make dev-up
```

Open **http://localhost:3000**

- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Stop the stack: `make dev-down`

## Advanced / manual development

If you prefer running API or web on the host (without Docker for those services):

```bash
make db-up
make db-migrate
source .venv/bin/activate
pnpm dev:api    # terminal 1 — http://127.0.0.1:8000
pnpm dev:web    # terminal 2 — http://localhost:3000
```

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

## Development commands

| Command | Description |
|---------|-------------|
| `make install` | Install Python + pnpm deps, create `.env` if missing |
| `make dev-up` | Start PostgreSQL, migrate, API, and web |
| `make dev-down` | Stop stack (keeps database data) |
| `make dev-logs` | Follow service logs |
| `make db-migrate` | Run Alembic migrations |
| `make test` | Run pytest |
| `make typecheck` | Frontend typecheck |
| `make build` | Frontend production build |

## MCP

Requires PostgreSQL running (`make db-up` or `make dev-up`):

```bash
pnpm mcp
```

## Documentation

- [Development guide](docs/development-guide.md)
- [Development infrastructure report](docs/development-infrastructure-report.md)
- [Current architecture](docs/current-architecture.md)
- [Migration map](docs/migration-map.md)
