# Development Guide — AI-CIO

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
docker compose up -d
alembic upgrade head
```

Run the API (seeds the instrument on startup):

```bash
python -m ai_cio.api
```

Run the unified Streamlit UI in another terminal:

```bash
streamlit run frontend/app.py
```

Open http://localhost:8501. The UI talks to FastAPI at http://127.0.0.1:8000.

## How to add a migration

1. Edit `ai_cio/db/models.py` to add/change columns or tables.
2. Generate a revision:

```bash
alembic revision --autogenerate -m "describe the change"
```

3. Inspect the generated file in `alembic/versions/` and fix any incorrect autogenerate output.
4. Apply it:

```bash
alembic upgrade head
```

5. If you added a money column, update `tests/test_canonical_schema.py` so it asserts `Numeric`.

## How to add an endpoint

1. Add the route in `ai_cio/api/routes.py`.
2. Add request/response models in `ai_cio/api/schemas.py` if the payload is new.
3. Put the business logic in `ai_cio/services/`.
4. Add or update tests in `tests/`.
5. Update the relevant doc in `docs/`.

## Change control rule

Before making any change:

1. **Inspect existing code first** — find the canonical module that already owns the behavior.
2. **Reuse** — extend existing services and models rather than creating parallel paths.
3. **Explain** — write down why the change is needed in the PR or commit message.
4. **Document** — update the matching file in `docs/`.
5. **Test** — add or update tests that cover the change.

## Running tests

```bash
pytest -q
```

Integration tests will try to start PostgreSQL via Docker; if Docker is unavailable they fall back to SQLite in-memory.
