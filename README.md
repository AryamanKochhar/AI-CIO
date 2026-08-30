# AI-CIO

One product, one application, one user identity.

AI-CIO is a human-in-the-loop personal financial decision-support system. It walks a person through psychometric onboarding, finances, goals, and document upload inside a single UI, then assembles a Digital Financial Twin for human review.

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

After changing `package.json`, `pnpm-lock.yaml`, or Dockerfiles:

```bash
make dev-build
make dev-up
```

Stop the stack: `make dev-down`

## Architecture

```text
Browser → Next.js (web) → FastAPI (api) → PostgreSQL
MCP (host) → same domain layer → PostgreSQL
```

## Development commands

| Command | Description |
|---------|-------------|
| `make install` | Install Python + pnpm deps, create `.env` |
| `make dev-build` | Build Docker images (api + web) |
| `make dev-up` | Start postgres, migrate, api, web |
| `make dev-down` | Stop stack (keeps database data) |
| `make dev-logs` | Follow service logs |
| `make db-migrate` | Run Alembic migrations |
| `make test` | Run pytest |
| `make typecheck` | Frontend typecheck |
| `make build` | Frontend production build |

## Documentation

- [Development guide](docs/development-guide.md)
- [Development infrastructure report](docs/development-infrastructure-report.md)
