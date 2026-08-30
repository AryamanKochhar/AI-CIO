# Local Development — AI-CIO

## Canonical command

```bash
make install
make dev-up
```

Open http://localhost:3000

## Rules

1. **One PostgreSQL** — only the `postgres` service in root `docker-compose.yml`
2. **No SQLite runtime** — `DATABASE_URL` must point to PostgreSQL
3. **No Parv / Streamlit** — deprecated; not part of dev stack
4. **MCP on host** — uses `DATABASE_URL` with `localhost:5432`; does not start another DB

## URL rules

| Context | API URL |
|---------|---------|
| Browser / `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` |
| API container → Postgres | `postgresql://...@postgres:5432/ai_cio` |
| Host tools (pytest, MCP, alembic) | `postgresql://...@localhost:5432/...` |

## When changing infrastructure

- Update `docker-compose.yml`, `.env.example`, `Makefile`, and `docs/development-guide.md` together
- Do not add a second postgres service or compose file
- Run `make test`, `make typecheck`, `make build` before finishing

## Debugging

```bash
make dev-logs SERVICE=postgres
make dev-logs SERVICE=api
docker compose ps
```

## Full guide

See [docs/development-guide.md](../docs/development-guide.md).
