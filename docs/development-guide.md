# Development Guide — AI-CIO

One product, one command: `make dev-up` starts PostgreSQL, migrations, API, and Next.js.

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | Latest | PostgreSQL, API, and web containers |
| Python | 3.12+ | Backend, Alembic, pytest, MCP |
| pnpm | 9.x | Frontend monorepo |
| Make | Any | Developer commands |

Optional: `curl`, `lsof` (used by startup scripts for health and port checks).

## 2. Installation

```bash
git clone <repo-url>
cd AI-CIO
make install
```

`make install`:

- Creates `.venv` and installs Python dependencies from `requirements.txt`
- Runs `pnpm install`
- Copies `.env.example` → `.env` only if `.env` does not exist
- Warns if Docker is missing (required for `make dev-up`)

## 3. Environment setup

Copy and edit `.env` if needed:

```bash
cp .env.example .env   # skipped automatically by make install if .env exists
```

Key variables:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL credentials |
| `DATABASE_URL` | Host-side DB URL (`localhost:5432`) for Alembic, MCP, pytest |
| `TEST_DATABASE_URL` | Separate test database on the **same** PostgreSQL instance |
| `API_PUBLIC_URL` | Browser-facing API URL (`http://localhost:8100`) |
| `API_INTERNAL_URL` | Container-to-container API URL (`http://api:8000`) |
| `NEXT_PUBLIC_API_BASE_URL` | Next.js client-side API base (must be browser-reachable) |
| `API_PORT`, `WEB_PORT`, `POSTGRES_PORT` | Local port mappings |

**Inside Docker**, services use hostname `postgres`, not `localhost`. The compose file sets `DATABASE_URL` for `api` and `migrate` automatically.

**From your host** (MCP, manual Alembic, pytest), use `localhost:5432`.

## 4. Docker architecture

```text
make dev-up
    │
    ▼
docker compose (project: ai-cio)
    │
    ├── postgres      ← ONE canonical PostgreSQL (persistent volume: postgres_data)
    ├── migrate       ← runs `alembic upgrade head` once, then exits
    ├── api           ← FastAPI (waits for migrate)
    └── web           ← Next.js dev server (waits for API health)
```

Deprecated stacks (Streamlit, Parv) are **not** part of this compose project.

## 5. Starting AI-CIO

```bash
make dev-up
```

Then open:

- **App:** http://localhost:3100
- **API:** http://localhost:8100
- **API docs:** http://localhost:8100/docs

Startup order: PostgreSQL healthy → migrations → API healthy → web ready.

## 6. Stopping AI-CIO

```bash
make dev-down
```

Stops containers but **preserves** the `postgres_data` volume. Your development data remains.

## 7. Logs

```bash
make dev-logs              # all services
make dev-logs SERVICE=api  # one service
```

Services: `postgres`, `migrate`, `api`, `web`.

## 8. Database

- **One PostgreSQL container:** `ai_cio_postgres`
- **Development database:** `ai_cio` (from `POSTGRES_DB`)
- **Test database:** `ai_cio_test` (same container, separate database)

Verify only one Postgres instance from this project:

```bash
docker compose ps
docker ps --filter name=ai_cio
```

## 9. Migrations

Migrations run automatically on `make dev-up` via the `migrate` service.

Manual migration:

```bash
make db-migrate
```

Create a new migration after model changes:

```bash
source .venv/bin/activate
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## 10. Testing

```bash
make test
```

This starts PostgreSQL (postgres service only), waits for health, and runs `pytest -q` against `ai_cio_test`.

Frontend quality gate:

```bash
make typecheck
make lint
make build
```

## 11. Frontend development

Default path: use `make dev-up` — no separate terminal needed.

Advanced (host-side hot reload without Docker web container):

```bash
make db-up
make db-migrate
pnpm dev:api    # terminal 1
pnpm dev:web    # terminal 2
```

Ensure `.env` has `NEXT_PUBLIC_API_BASE_URL=http://localhost:8100`.

## 12. Backend development

Default path: API runs in Docker via `make dev-up`.

Advanced host-side API:

```bash
make db-up && make db-migrate
source .venv/bin/activate
pnpm dev:api
```

Requires `DATABASE_URL` pointing at `localhost:5432` in `.env`.

## 13. MCP development

MCP uses the same PostgreSQL and domain layer. It does **not** start another database.

```bash
make db-up    # if stack not already running
pnpm mcp
```

Ensure `.env` has `DATABASE_URL=postgresql://...@localhost:5432/ai_cio`.

## 14. Troubleshooting

| Issue | What to do |
|-------|------------|
| Port 5432 in use | Stop conflicting Postgres (`brew services stop postgresql`) or change `POSTGRES_PORT` in `.env` |
| Port 3100 / 8100 in use | Choose unused `WEB_PORT` / `API_PORT` values; Orbix ports 3000, 8000 and 18000 are reserved |
| Postgres unhealthy | `make dev-logs SERVICE=postgres` |
| Alembic failure | Check `DATABASE_URL`, run `make db-migrate` |
| API cannot connect | Ensure API uses `postgres:5432` inside Docker; host uses `localhost:5432` |
| Frontend cannot reach API | `NEXT_PUBLIC_API_BASE_URL` must be `http://localhost:8100` (browser, not `api:8000`) |
| Docker not running | Start Docker Desktop |
| `.env` missing | `make install` or `cp .env.example .env` |
| Docker daemon not running | Open Docker Desktop manually; wait until `docker info` shows **Server Version**. Then `make dev-up`. |
| Docker Desktop I/O / build errors | Fixed by no-build compose. If daemon is stuck: Docker Desktop → Troubleshoot → **Restart Docker Desktop** |
| Legacy `ai_cio_db` container | `docker stop ai_cio_db` then `make dev-up` |

### Removing old AI-CIO containers safely

List project containers:

```bash
docker compose ps -a
docker ps --filter name=ai_cio
```

Stop this project only:

```bash
make dev-down
```

Do **not** run `docker system prune` unless you understand it removes unused containers/images globally.

### Legacy Parv / Streamlit

`parv-main/` and Streamlit `frontend/` were removed. If you still have old containers from other projects, they are unrelated — check names before stopping.

## 15. Resetting local database

**WARNING:** destroys all local AI-CIO development data.

```bash
make db-reset
```

Type `reset` when prompted. This runs `docker compose down -v`, recreates PostgreSQL, and applies migrations.

## 16. Common errors

**`DATABASE_URL is required`**

Copy `.env.example` to `.env` or run `make install`.

**`SQLite is not supported`**

Runtime must use PostgreSQL. Remove any `sqlite://` URL from `.env`.

**`PostgreSQL is required for integration tests`**

Run `make db-up` or `make dev-up` before `pytest`.

**Migration race / duplicate migrate**

Only the `migrate` service runs Alembic. The API container does not run migrations on startup.

## Makefile reference

| Command | Description |
|---------|-------------|
| `make install` | Install deps, create `.env` if missing |
| `make dev-up` | Start full stack |
| `make dev-down` | Stop stack, keep data |
| `make dev-restart` | Restart full stack |
| `make dev-logs` | Follow logs |
| `make db-up` | Start PostgreSQL only |
| `make db-down` | Stop PostgreSQL |
| `make db-migrate` | Run Alembic |
| `make db-reset` | Destroy and recreate DB (destructive) |
| `make test` | pytest |
| `make lint` | pnpm lint |
| `make typecheck` | pnpm typecheck |
| `make build` | pnpm build |
| `make clean` | Remove build artifacts |
