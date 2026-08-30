# Data Model — AI-CIO

Canonical SQLAlchemy models live in `ai_cio/db/models.py`. The database is PostgreSQL; Alembic migrations live in `alembic/versions/`.

General conventions:

- All money columns are `Numeric` (never `Float`).
- `JSONB` (with a generic `JSON` fallback for non-Postgres tests) is used for instrument payloads, polarity, warnings, and constraint payloads.
- All datetimes are timezone-aware (`DateTime(timezone=True)`).

## Tables

### `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Canonical user identity. |
| `name` | String(255) | Display name. |
| `email` | String(320), nullable, unique, indexed | Added for MVP auth. |
| `password_hash` | String(255), nullable | PBKDF2-HMAC-SHA256 hash; no plaintext passwords. |
| `created_at` | DateTime(tz) | Created timestamp. |
| `updated_at` | DateTime(tz) | Updated timestamp. |

### `instruments`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Instrument row. |
| `version` | String(32), unique | e.g., `1.0`. |
| `payload` | JSONB | Full question bank JSON including option scores. |
| `created_at` | DateTime(tz) | Created timestamp. |

### `assessment_sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Session id. |
| `user_id` | FK users.id | Owner. |
| `instrument_id` | FK instruments.id | Instrument used. |
| `status` | String(32) | `in_progress`, `completed`, `abandoned` (check constraint). |
| `started_at` | DateTime(tz) | Start time. |
| `completed_at` | DateTime(tz), nullable | Completion time. |

### `assessment_responses`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Response row. |
| `session_id` | FK assessment_sessions.id | Session. |
| `question_id` | String(16) | e.g., `Q001`. |
| `answer_id` | String(32) | The option id chosen by the user. |
| `score_applied` | Float | The score mapped server-side from the instrument. Distinct from `answer_id`. |
| `confidence` | Integer | 0–100. |
| `response_time_ms` | Integer | Milliseconds. |
| `created_at` | DateTime(tz) | Timestamp. |

Unique constraint: `(session_id, question_id)`. Check constraint: `confidence BETWEEN 0 AND 100`.

### `behavioral_profiles`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Profile id. |
| `session_id` | FK assessment_sessions.id, unique | One profile per completed session. |
| `user_id` | FK users.id | Owner. |
| `instrument_id` | FK instruments.id | Instrument version used. |
| `risk_score` | Float | 0–100. |
| `loss_aversion_score` | Float | 0–100. |
| `anchoring_score` | Float | 0–100. |
| `recency_bias_score` | Float | 0–100. |
| `herding_score` | Float | 0–100. |
| `overconfidence_score` | Float | 0–100. |
| `decision_stability_score` | Float | 0–100. |
| `average_confidence` | Float | Mean user-reported confidence. |
| `average_response_time_ms` | Float | Mean response time. |
| `profile_confidence` | Float | Composite reliability estimate. |
| `polarity` | JSONB | Explicit per-dimension higher/lower meaning so downstream readers cannot invert scores. |
| `created_at` | DateTime(tz) | Timestamp. |

### `documents`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Document id. |
| `user_id` | FK users.id | Owner. |
| `kind` | String(32) | `cas_pdf`, `nsdl_statement`, `cdsl_statement`, `other`. |
| `filename` | String(512) | Original filename. |
| `parser_version` | String(64), nullable | e.g., `cas-v1`. |
| `checksum` | String(128), nullable | SHA-256 of uploaded bytes. |
| `warning_json` | JSONB, nullable | Parser warnings. |
| `status` | String(32) | `pending`, `processing`, `extracted`, `needs_review`, `failed` (check constraint). |
| `validation_status` | String(32), nullable | `unvalidated`, `valid`, `partial`, `invalid` (check constraint). |
| `ingested_at` | DateTime(tz) | Upload timestamp. |

### `source_pages`

Raw extracted page text for traceability. Never exposed via API/MCP.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Row id. |
| `document_id` | FK documents.id | Parent document. |
| `user_id` | FK users.id | Owner. |
| `page` | Integer | One-based PDF page. |
| `text` | Text | Raw extracted text. |

Unique constraint: `(document_id, page)`.

### `funds`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Fund id. |
| `user_id` | FK users.id | Owner. |
| `document_id` | FK documents.id | Source document. |
| `amc` | Text | Asset management company. |
| `folio` | Text | Folio number. |
| `scheme_name` | Text | Scheme name. |
| `isin` | Text, nullable | ISIN. |

Unique constraint: `(document_id, amc, folio, scheme_name, isin)`.

### `holdings`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Holding id. |
| `user_id` | FK users.id | Owner. |
| `document_id` | FK documents.id | Source document. |
| `fund_id` | FK funds.id | Fund. |
| `opening_units` | Numeric, nullable | Units at start. |
| `closing_units` | Numeric, nullable | Units at end. |
| `nav` | Numeric, nullable | NAV. |
| `valuation` | Numeric, nullable | Market value. |
| `valuation_date` | String(32), nullable | CAS valuation date string. |
| `source_page` | Integer | One-based page where parsed. |

### `transactions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Transaction id. |
| `user_id` | FK users.id | Owner. |
| `document_id` | FK documents.id | Source document. |
| `fund_id` | FK funds.id | Fund. |
| `date` | String(32), nullable | CAS date string. |
| `transaction_type` | String(64) | e.g., `SIP_PURCHASE`, `REDEMPTION`, `FAILED_PAYMENT`. |
| `description` | Text | Raw description. |
| `amount` | Numeric, nullable | Amount. |
| `units` | Numeric, nullable | Units. |
| `nav` | Numeric, nullable | NAV. |
| `unit_balance` | Numeric, nullable | Running balance. |
| `source_page` | Integer | One-based page where parsed. |

### `goals`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Goal id. |
| `user_id` | FK users.id | Owner. |
| `name` | String(255), nullable | Goal name. |
| `goal_type` | String(64), nullable | Check constraint allows: `emergency`, `retirement`, `education`, `home`, `vehicle`, `travel`, `wealth`, `other`. |
| `target_amount` | Numeric, nullable | Target amount. |
| `target_date` | String(32), nullable | Target date. |
| `current_funding` | Numeric, nullable | Current funding. |
| `priority` | String(32), nullable | `high`, `medium`, `low`. |
| `flexibility` | String(32), nullable | `fixed`, `somewhat`, `flexible`. |
| `horizon_years` | Integer, nullable | Horizon in years. |
| `notes` | Text, nullable | Notes. |
| `created_at` | DateTime(tz) | Timestamp. |

### `cashflows`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Cashflow id. |
| `user_id` | FK users.id | Owner. |
| `kind` | String(32), nullable | `income`, `expense`, `liquid`. |
| `amount` | Numeric, nullable | Amount. |
| `cadence` | String(32), nullable | `monthly`, `annual`, `once`. |
| `notes` | Text, nullable | Notes. |
| `created_at` | DateTime(tz) | Timestamp. |

### `liabilities`

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Liability id. |
| `user_id` | FK users.id | Owner. |
| `name` | String(255), nullable | Name. |
| `balance` | Numeric, nullable | Outstanding balance. |
| `monthly_payment` | Numeric, nullable | EMI / monthly payment. |
| `notes` | Text, nullable | Notes. |
| `created_at` | DateTime(tz) | Timestamp. |

### `constraints`

Reserved for future hard constraints. Not used as a user-facing dashboard in the MVP.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Constraint id. |
| `user_id` | FK users.id | Owner. |
| `kind` | String(64), nullable | Constraint kind. |
| `payload` | JSONB, nullable | Constraint payload. |
| `notes` | Text, nullable | Notes. |
| `created_at` | DateTime(tz) | Timestamp. |

### `user_journeys`

Tracks onboarding position and explicit skip/unknown flags.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Journey id. |
| `user_id` | FK users.id, unique | One journey per user. |
| `current_step` | String(32) | Current UI step. |
| `finances_status` | String(32) | `not_started`, `provided`, `skipped`. |
| `goals_status` | String(32) | `not_started`, `provided`, `skipped`. |
| `portfolio_status` | String(32) | `not_started`, `provided`, `skipped`. |
| `decision` | String(32), nullable | Final decision: `accept`, `modify`, `reject`. |
| `decision_notes` | Text, nullable | Decision notes. |
| `updated_at` | DateTime(tz) | Updated timestamp. |

## Migrations

| Revision | File | Purpose |
|----------|------|---------|
| `0001_canonical` | `alembic/versions/0001_canonical_schema.py` | Creates the canonical schema (users, instruments, assessments, documents, portfolio, goals, cashflows, liabilities, constraints). |
| `0002_journey` | `alembic/versions/0002_journey.py` | Adds `user_journeys`, plus goal fields (`goal_type`, `target_date`, `current_funding`, `priority`, `flexibility`) and `liabilities.monthly_payment`. |
| `0003_auth_documents` | `alembic/versions/0003_auth_and_documents.py` | Adds `users.email` and `users.password_hash`; adds `documents.status` and `documents.validation_status` with check constraints; adds `goals.goal_type` check constraint. |
