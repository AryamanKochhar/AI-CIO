# Development Infrastructure Report — AI-CIO

> August 2026 — unified local development stack

## 1. Previous development architecture

Developers manually ran:

```bash
docker compose up -d          # postgres only
alembic upgrade head          # separate terminal step
pnpm dev:api                  # terminal 1
pnpm dev:web                  # terminal 2
```

`docker-compose.yml` contained **only** PostgreSQL. No API or web containers. No Makefile. No single startup command.

## 2. Problems discovered

| Problem | Impact |
|---------|--------|
| Custom Docker image builds | Docker Desktop I/O errors during `docker compose build` on some machines |
| Repo path contains spaces (`AI CIO`) | Broke `$DOCKER` command wrapper — Docker calls failed instantly |
| Unguarded `docker ps` / `docker info` | Hung indefinitely when Docker Desktop was frozen |
| Docker daemon not ready | Client installed but engine not running — compose failed |

## 3. Root cause of duplicate Postgres

The project had **one** compose file with **one** postgres service. Duplicate Postgres risk came from:

1. **Manual host PostgreSQL** on port 5432 conflicting with Docker postgres
2. **`tests/conftest.py`** auto-starting compose (same service, but opaque to developers)
3. **GitHub Actions CI** using its own ephemeral postgres service (CI-only, not local duplicate)
4. **Historical Parv compose** (removed with `parv-main/`)

There was no second AI-CIO compose file, but developers could accidentally run system Postgres + Docker Postgres on the same port.

## 4. Final Docker architecture

Development uses **official base images** with the repo bind-mounted — no custom image build step:

- `postgres:15-alpine`
- `python:3.12-slim` (api + migrate)
- `node:20-alpine` (web)

Dependencies install at container start (cached via named volumes). This avoids Docker Desktop build-cache export I/O failures.

## 5. Final Compose services

| Service | Container | Purpose |
|---------|-----------|---------|
| `postgres` | `ai_cio_postgres` | Canonical PostgreSQL 15 |
| `migrate` | `ai_cio_migrate` | `alembic upgrade head` (once per up) |
| `api` | `ai_cio_api` | FastAPI on port 8000 |
| `web` | `ai_cio_web` | Next.js dev on port 3000 |

## 6. Database strategy

- **One PostgreSQL container** with volume `postgres_data`
- **Development DB:** `ai_cio`
- **Test DB:** `ai_cio_test` on the same instance (created by pytest fixture)
- **No SQLite runtime** — settings fail fast if `DATABASE_URL` missing or sqlite
- **Inside Docker:** `@postgres:5432`
- **From host:** `@localhost:5432`

## 7. Environment strategy

Single source: `.env` (from `.env.example`).

- Host tools use `DATABASE_URL` with `localhost`
- Compose overrides `DATABASE_URL` for `api`/`migrate` with `postgres` hostname
- Browser uses `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Future SSR server routes can use `API_INTERNAL_URL=http://api:8000`

## 8. Makefile commands

See `docs/development-guide.md` for full reference. Primary commands: `install`, `dev-up`, `dev-down`, `db-migrate`, `test`.

## 9. Startup flow

1. `make dev-up` loads `.env`
2. Port conflict check (if port busy and not our container → error)
3. `docker compose up -d --build`
4. Wait for PostgreSQL (`pg_isready`)
5. `migrate` completes (`alembic upgrade head`)
6. API starts, healthcheck `GET /health`
7. Web starts, readiness via HTTP :3000

## 10. Shutdown flow

`make dev-down` → `docker compose down` — containers removed, **volume preserved**.

## 11. Migration strategy

- **Authoritative runner:** `migrate` service only
- API lifespan seeds instrument data but does **not** run Alembic
- `make db-migrate` runs `docker compose run --rm migrate`
- Idempotent: `alembic upgrade head` safe on repeated runs

## 12. Health checks

| Service | Check |
|---------|-------|
| postgres | `pg_isready` |
| api | `GET /health` |
| web | HTTP readiness script after compose start |

Compose `depends_on` with `condition: service_healthy` / `service_completed_successfully`.

## 13. Port strategy

Defaults: `POSTGRES_PORT=5432`, `API_PORT=8000`, `WEB_PORT=3000`. Configurable via `.env`. Clear error if port occupied by non-project process.

## 14. MCP integration

MCP runs on host via `pnpm mcp`. Connects to `localhost:5432` using `DATABASE_URL` from `.env`. No additional database container.

## 15. Streamlit / Parv status

- `frontend/` (Streamlit): **deleted**
- `parv-main/`: **deleted**
- Not started by `make dev-up`

## 16. Testing

- `make test` starts postgres only, runs pytest against `ai_cio_test`
- SQLite fallback **removed** from conftest
- CI unchanged: ephemeral postgres service on GitHub Actions

## 17. E2E verification

After `make dev-up`, verify manually:

1. Register / login at http://localhost:3000
2. Complete psychometric, finances, goals, documents, review, twin
3. `make dev-down` → `make dev-up` → login → data persists

## 18. Troubleshooting

Documented in `docs/development-guide.md` §14–16.

## 19. Remaining technical debt

| Item | Notes |
|------|-------|
| Web in Docker uses volume mounts for hot reload | Slightly slower first start |
| No frontend automated tests | Manual E2E only |
| MCP not containerized | Host process by design |
| Production deployment | Out of scope for this task |

## 20. Future production considerations

- Separate production compose or orchestrator
- Secrets via vault, not `.env`
- `next build` + `next start` production web image
- API behind reverse proxy with TLS
- Managed PostgreSQL instead of container volume
