# AI-cio

**Powered by Orbix**

![AI-cio — Powered by Orbix](apps/web/public/brand/ai-cio-logo.svg)

One product, one application, one user identity.

AI-cio is a human-in-the-loop personal financial decision-support system. It walks a person through psychometric onboarding, finances, goals, and document upload inside a single UI, then assembles a Digital Financial Twin for human review.

The web identity is configured in `apps/web/src/lib/brand.ts`; API documentation
and notification branding use the product constants in `apps/api/ai_cio/settings.py`.
See [logo assets and branding configuration](docs/branding.md).

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

## Windows local development

Use Python 3.11+ and Node.js 22 for the native TypeScript test runner. Store real
credentials in the ignored root `.env`; `.env.example` contains placeholders.

```powershell
.\scripts\dev-local.ps1 -Setup
.\scripts\dev-local.ps1
.\scripts\dev-local.ps1 -Stop
```

The PowerShell launcher creates the virtual environment, installs locked Node
dependencies and applies migrations during setup. It starts hidden API/web
processes, checks both health endpoints and writes logs under `.dev/`. It stops
only process trees that it started. An occupied port produces an error rather
than terminating another application. The API and web bind to localhost by default.

Use `-EnvFile .env.preview` for a separate ignored development configuration and
`-SkipMigrations` when setup should not apply migrations. `-Production` starts an
already-built web application through the same launcher. Explicit process
environment variables override file values; `AICIO_ENV_FILE` selects the API file.

Tests require a separate PostgreSQL database whose name ends in `_test`. They
ignore the live `.env` and never inherit its shared database or provider keys.
Set `TEST_DATABASE_URL` and `POSTGRES_ADMIN_URL` explicitly when the local test
server uses a different port.

The synthetic personas, growing companion, decision workflow and financial
source boundaries are documented in [product improvements](docs/product-improvements.md)
and [finance standards](docs/finance-standards.md).

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
