# Development Guide — AI-CIO

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pnpm install
cp .env.example .env
docker compose up -d
alembic upgrade head
```

## Run (canonical)

Terminal 1 — API:

```bash
python -m ai_cio.api
```

Terminal 2 — Web:

```bash
pnpm dev:web
```

- API: http://127.0.0.1:8000
- Web: http://localhost:3000

## Run (legacy Streamlit — deprecated)

```bash
streamlit run frontend/app.py
```

## Tests

```bash
pytest -q           # backend
pnpm typecheck      # frontend types
pnpm lint           # frontend lint
pnpm build          # frontend production build
```

## How to add a migration

1. Edit `ai_cio/db/models.py`.
2. `alembic revision --autogenerate -m "describe the change"`
3. Review generated file in `alembic/versions/`.
4. `alembic upgrade head`
5. Run `pytest -q`.

## Monorepo commands

| Command | Purpose |
|---------|---------|
| `pnpm install` | Install JS/TS workspace |
| `pnpm dev:web` | Next.js dev server |
| `pnpm dev:api` | Alias for `python -m ai_cio.api` |
| `pnpm test:api` | Run pytest |
| `pnpm migrate` | Run Alembic migrations |
| `pnpm build` | Build web app via Turborepo |

## MCP

```bash
python server.py
```

Uses the same PostgreSQL domain layer as the API.
