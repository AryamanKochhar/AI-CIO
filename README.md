# AI-CIO

One product, one application, one user identity.

AI-CIO is a human-in-the-loop personal financial decision-support system. It walks a person through psychometric onboarding, finances, goals, and CAS upload inside a single UI, then stops for human review. It does not place trades and it does not invent missing numbers.

## Run the product

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
docker compose up -d
alembic upgrade head

# Terminal 1 — API (seeds the psychometric instrument on startup)
python -m ai_cio.api

# Terminal 2 — unified UI
streamlit run frontend/app.py
```

Open http://localhost:8501. The UI talks only to FastAPI at http://127.0.0.1:8000.

Stay inside this app for the whole journey. Do not run `parv-main/frontend/app.py` — that file only points here.

```bash
pytest -q
```

## What the user does

1. Understand me — questionnaire from the API (the browser never scores).
2. My finances — income, expenses, liquid savings, optional liabilities. Blank stays unknown.
3. My goals — one or more goals; skip if unknown.
4. My portfolio — MFCentral CAS PDF upload, extraction, review.
5. Review — known / unknown, user-provided / CAS-derived / system-derived.
6. Analysis — placeholder until reasoning exists (no invented ₹1,00,000 plan).
7. Review & decide — accept / modify / reject, persisted on the same `user_id`.

## Architecture

```text
Streamlit (frontend/app.py)
        │  HTTP
        ▼
FastAPI (python -m ai_cio.api)
        │
        ▼
PostgreSQL  (canonical schema, one user_id)
        ▲
        │  read-only facts
MCP (python server.py)  — model integration, not a second product
```

Domain logic lives in `ai_cio/`. CAS parsing stays in `parser.py` / `analysis.py`. Psychometric scoring stays in `ai_cio/psychometrics/` and uses `instruments/v1.0.json`.

MCP is an integration interface for model access to financial facts. It is not a user-facing dashboard. Default CAS ingest is `python scripts/ingest.py data/cas.pdf --user-id N` into Postgres. `--sqlite` remains only for the legacy local file.

See [architecture.md](docs/architecture.md), [data-flow.md](docs/data-flow.md), [mcp-tools.md](docs/mcp-tools.md), and [privacy-and-limitations.md](docs/privacy-and-limitations.md).
