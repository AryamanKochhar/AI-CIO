# Target Architecture — AI-CIO

> Status: **IMPLEMENTED now**. This is the current target architecture after the unification / Step 1–4 pass.

## What is built

AI-CIO is one repo, one application, one PostgreSQL database, and one user identity.

```text
USER → UNIFIED STREAMLIT UI → FASTAPI → DOMAIN LAYER (identity, psychometrics, finances, goals, documents, portfolio, twin) → POSTGRESQL
MCP → DOMAIN → POSTGRESQL
```

- **UI layer**: `frontend/app.py` is the single Streamlit app. It owns rendering and transient session state; all business logic lives in the API/domain.
- **API layer**: `ai_cio/api/` is the canonical FastAPI application (`python -m ai_cio.api`). Routes adapt HTTP to domain services.
- **Domain layer**: `ai_cio/services/` and `ai_cio/psychometrics/` contain the business logic. `parser.py` / `analysis.py` at the project root are domain-owned parsing/analysis utilities used by services and MCP.
- **Database layer**: `ai_cio/db/` defines SQLAlchemy 2.0 models and sessions. PostgreSQL is the system of record.
- **MCP interface**: `server.py` exposes read-only tools over stdio. It calls the same domain services; it is not a second product.

## Dependency direction

```text
UI (Streamlit) → API (FastAPI) → Domain (ai_cio/services) → Database (ai_cio/db)
MCP → Domain → Database
```

Domain modules do not depend on the UI, API, or MCP. `parser.py` and `analysis.py` are plain Python utilities used by domain services.

## Module map

| Path | Responsibility |
|------|----------------|
| `ai_cio/db/base.py` | SQLAlchemy declarative base. |
| `ai_cio/db/models.py` | Canonical models (users, instruments, assessments, documents, portfolio, goals, cashflows, liabilities, constraints, user journeys). |
| `ai_cio/db/session.py` | Lazy engine/session factory (`configure_engine`, `get_session`, `get_db`). |
| `ai_cio/api/main.py` | FastAPI app factory, CORS, lifespan (seeds instrument). |
| `ai_cio/api/routes.py` | HTTP routes: `/auth/*`, `/users/*`, `/assessments/*`, `/instruments/*`, `/admin/*`. |
| `ai_cio/api/schemas.py` | Pydantic request/response models. |
| `ai_cio/services/identity.py` | User registration, login, PBKDF2 password hashing, user resolution. |
| `ai_cio/services/instruments.py` | Instrument seeding and public question payload (no scores). |
| `ai_cio/services/assessments.py` | Assessment lifecycle, response submission, server-side scoring. |
| `ai_cio/services/finances.py` | Cashflows and liabilities (income, expenses, liquid, debts). |
| `ai_cio/services/goals.py` | Goal CRUD and serialization. |
| `ai_cio/services/journey.py` | Onboarding step/state persistence. |
| `ai_cio/services/portfolio.py` | CAS persistence, holdings, transactions, document count. |
| `ai_cio/services/documents.py` | Unified document ingestion contract (CAS parsed; NSDL/CDSL/other stored with parser pending). |
| `ai_cio/services/review.py` | Human-readable review assembly (proto-Twin). |
| `ai_cio/services/twin.py` | Digital Financial Twin assembly. |
| `ai_cio/psychometrics/` | Pure scoring logic: instrument loader, scoring, polarity, observations. |
| `ai_cio/seed.py` | One-off instrument seed. |
| `ai_cio/settings.py` | Runtime settings from `.env`. |
| `parser.py` | CAS PDF parser for MFCentral CAMS/KFintech statements. Domain-owned utility. |
| `analysis.py` | Portfolio calculations (total value, allocation, concentration, SIP summary, validation helpers). Domain-owned utility. |
| `server.py` | MCP server entry point (stdio). |
| `frontend/` | Unified Streamlit UI (`frontend/app.py`, `frontend/client.py`). |
| `scripts/ingest.py` | CLI CAS ingest into PostgreSQL (legacy `--sqlite` branch retained). |
| `instruments/` | Versioned psychometric instrument (e.g., `instruments/v1.0.json`). |
| `knowledge/` | Static educational Markdown used by MCP `search_knowledge`. |
| `tests/` | pytest suite: schema contracts, scoring polarity, API integration, CAS persistence, user isolation, MCP reads. |
| `docs/` | Architecture, data-flow, security, and product documentation. |
| `data/` | Sample CAS PDFs and legacy SQLite files (not the runtime database). |
| `skills/` | Not present in the current tree. |

## What is deliberately NOT built

These are intentionally out of scope for the current MVP:

- Microservices or service mesh.
- Redis, Kafka, RabbitMQ, or other message brokers.
- Vector database.
- Autonomous AI agents or agent orchestration.
- Live market-data feeds or real-time price streaming.
- Automated trade execution.
- Multi-tenant identity or OAuth provider integration (MVP auth is local email/password with PBKDF2).

Everything above is future work and is documented in `future-architecture.md` and `future-research.md` as **PLANNED**, not implemented.
