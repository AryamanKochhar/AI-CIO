# Current Architecture — AI-CIO

> Status: discovery document produced before the unification / Step 1–4 implementation pass.

## Executive summary

The repository already contains a **partially unified** AI-CIO application. The canonical runtime is a FastAPI backend backed by PostgreSQL, consumed by a single Streamlit UI. Psychometric scoring has been corrected and instrument-driven, portfolio ingestion is document-scoped and user-scoped, and a first review/completeness view exists.

However, several gaps remain versus the target:

* Authentication is name-only; there is no login/register with password handling.
* Document ingestion supports only `cas_pdf`; NSDL/CDSL statements are not first-class document types.
* The "Digital Financial Twin" concept exists only implicitly inside the review service.
* Legacy files (`database.py`, root `server.py`, root `parser.py` consumed directly, `parv-main/`) still sit in the tree.
* The UI is functional but not yet premium / design-system driven.

## Current runtime entry points

| Entry point | Command | Purpose |
|-------------|---------|---------|
| API | `python -m ai_cio.api` | Canonical FastAPI server. Seeds instrument on startup. |
| UI | `streamlit run frontend/app.py` | Single Streamlit journey. |
| MCP | `python server.py` | Read-only model context protocol over stdio. |
| Seed | `python -m ai_cio.seed` | One-off instrument seed. |
| CLI ingest | `python scripts/ingest.py data/cas.pdf --user-id N` | Ingest CAS into Postgres (or `--sqlite` for legacy). |
| Legacy API | `python parv-main/backend/main.py` | Deprecated; re-exports canonical app with a warning. |
| Legacy UI | `streamlit run parv-main/frontend/app.py` | Deprecated landing page pointing to the new UI. |

## Current databases

### Canonical: PostgreSQL

* URL configured via `DATABASE_URL` / `.env`; default `postgresql://postgres:postgres@localhost:5432/ai_cio`.
* Managed with Alembic (`alembic/`).
* SQLAlchemy 2.0 ORM models in `ai_cio/db/models.py`.
* All money columns are `Numeric` / `Decimal`; no Float for money.

### Legacy: SQLite

* `database.py` creates `portfolio.db` / user-supplied path.
* Used only by `scripts/ingest.py --sqlite` and legacy tests (`test_database.py`).
* SQLite is **not** the runtime system of record.

## Current data flow

```text
User
 ↓
Streamlit UI (frontend/app.py)
 ↓ HTTP / REST
FastAPI (ai_cio/api/main.py → routes.py)
 ↓
Domain services (ai_cio/services/*.py)
 ↓
PostgreSQL (ai_cio/db/models.py)

MCP (server.py)
 ↓
Domain services / analysis
 ↓
PostgreSQL

CLI / scripts
 ↓
parser.py → ai_cio/services/portfolio.py
 ↓
PostgreSQL
```

## Current psychometric flow

1. `instruments/v1.0.json` defines 18 questions across 7 dimensions with explicit option `score` values.
2. API seeds the instrument via `ai_cio/services/instruments.py`.
3. `GET /instruments/current/questions` returns public questions **without** option scores.
4. `POST /assessments/start` creates an `AssessmentSession` for a `user_id`.
5. `POST /assessments/{id}/responses` stores `answer_id` and `score_applied`.
6. `POST /assessments/{id}/complete` calls `ai_cio/psychometrics/scoring.py` to compute the profile.
7. `GET /assessments/{id}/observations` returns plain-language observations.
8. Scores are stored in `behavioral_profiles`; polarity is stored as JSON.

Polarity is explicit and verified; higher scores on bias-labelled dimensions mean more adaptive / less biased behaviour.

## Current CAS flow

1. `parser.py` parses MFCentral CAMS/KFintech CAS PDFs with PyMuPDF.
2. Returns `ParseResult` (holdings, transactions, page text, warnings).
3. `analysis.py` computes totals, allocations, concentration, and validation helpers.
4. `ai_cio/services/portfolio.py` persists into `documents`, `source_pages`, `funds`, `holdings`, `transactions`.
5. Every row carries `user_id` and `document_id`; multiple documents per user are supported and never wipe other users.
6. API exposes `POST /users/{id}/documents/cas`, `GET /users/{id}/holdings`, etc.

## Current UI flow

The Streamlit app (`frontend/app.py`) presents a single journey:

```text
Welcome → Psychometrics → Finances → Goals → Portfolio → Review → Analysis → Decide
```

It talks only to FastAPI and stores only `user_id`, `session_id`, progress, and transient UI state in Streamlit session state.

## Current domain modules

| Module | Responsibility |
|--------|----------------|
| `ai_cio/db/models.py` | Canonical Postgres models (User, Instrument, AssessmentSession, AssessmentResponse, BehavioralProfile, Document, SourcePage, Fund, Holding, Transaction, Goal, Cashflow, Liability, Constraint, UserJourney). |
| `ai_cio/db/session.py` | SQLAlchemy engine/session helpers. |
| `ai_cio/services/identity.py` | User creation / lookup; `DEFAULT_USER_ID` fallback for single-user dev mode. |
| `ai_cio/services/instruments.py` | Seed and public payload for the instrument. |
| `ai_cio/services/assessments.py` | Assessment lifecycle and scoring orchestration. |
| `ai_cio/services/finances.py` | Cashflows and liabilities. |
| `ai_cio/services/goals.py` | Goal creation/deletion/serialization. |
| `ai_cio/services/journey.py` | Onboarding progress and decision capture. |
| `ai_cio/services/portfolio.py` | CAS persistence, holdings, transactions. |
| `ai_cio/services/review.py` | Assembles a human-readable review with completeness flags (proto-Twin). |
| `ai_cio/psychometrics/*` | Pure scoring logic (instrument, scoring, polarity, observations). |
| `ai_cio/api/routes.py` | HTTP routes. |
| `ai_cio/api/schemas.py` | Pydantic request/response models. |

## Current user identity handling

* `users.id` is the canonical identity.
* `User` model currently has only `id`, `name`, `created_at`, `updated_at`.
* No password, no email, no session token.
* The UI creates a user by entering a name; subsequent visits must re-enter the user id/name (no durable login).
* `DEFAULT_USER_ID` env var allows dev single-user fallback.

## Current duplicate / legacy functionality

| Legacy | Replacement | Status |
|--------|-------------|--------|
| `parv-main/backend/*` | `ai_cio/api/*` + `ai_cio/services/*` | Deprecated; `parv-main/frontend/app.py` redirects. |
| `parv-main/data/questions.json` | `instruments/v1.0.json` | Duplicate kept in sync by test. |
| `database.py` (SQLite) | `ai_cio/db/*` + PostgreSQL | Legacy persistence only. |
| `config.py` | `ai_cio/settings.py` | Legacy paths. |
| `scripts/ingest.py --sqlite` | `scripts/ingest.py` (Postgres default) | SQLite branch retained for migration/parity. |
| Root `server.py` | Same file but now canonical MCP | Kept at root for compatibility; imports canonical domain. |
| Root `parser.py` / `analysis.py` | Used by canonical services and MCP | Keep; document as domain-owned parsing/analysis. |

## Current test coverage

* 38 tests currently pass (see `pytest -q`).
* Tests cover: schema contracts, psychometric scoring polarity, answer-id vs score-applied, API integration, CAS persistence, user isolation, MCP domain reads, SQLite legacy roundtrip, parser units.
* Integration tests auto-start Postgres via Docker if `docker` is available; otherwise fall back to SQLite in-memory.

## Known technical debt

1. **Authentication gap**: no password / login / session durability.
2. **Document model limited to `cas_pdf`**: NSDL/CDSL not supported as first-class types.
3. **Twin is implicit**: review service mixes presentation and Twin assembly.
4. **Legacy files in root**: `database.py`, `config.py` invite confusion.
5. **UI lacks design system**: styles are inline; no reusable component helpers, assets, or polished empty/processing/error states.
6. **No explicit provenance model**: sources are hard-coded strings (`user-provided`, `cas-derived`, `system-derived`) rather than a structured provenance table.
7. **No password hashing / secrets management**.
8. **Analysis/decide steps are placeholders** until future AI-CIO reasoning exists.

## Safe-to-move / retain / deprecate notes

* **Keep** `parser.py` and `analysis.py` at root: they are imported by canonical services, tests, and MCP.
* **Deprecate** `parv-main/`: no runtime dependency uses it except the backward-compat redirect.
* **Deprecate** `database.py` and `config.py`: retain until root-level references are migrated to canonical equivalents.
* **Keep** `server.py` as the MCP entry point; consider moving to `ai_cio/mcp.py` later.
* **Keep** `frontend/` as the single UI package; rename to `app/` only if it simplifies paths without breaking imports.
