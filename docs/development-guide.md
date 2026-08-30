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

## Run

```bash
pnpm dev:api    # FastAPI at http://127.0.0.1:8000
pnpm dev:web    # Next.js at http://localhost:3000
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

## Migrations

1. Edit `apps/api/ai_cio/db/models.py`
2. `alembic revision --autogenerate -m "describe change"`
3. Review file in `alembic/versions/`
4. `alembic upgrade head`
5. `pytest -q`
