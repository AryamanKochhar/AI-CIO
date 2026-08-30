# Onboarding Flow — AI-CIO

> Status: **IMPLEMENTED** in `frontend/app.py` and the `/users/{id}/journey` API.

## User-visible phases

The Streamlit UI groups the journey into four top-level phases. These are the names the user sees:

1. **Understand me**
2. **My finances**
3. **My goals & portfolio**
4. **My AI-CIO profile**

## Internal step sequence

The internal `STEP_ORDER` in `frontend/app.py` is:

```text
auth → welcome → psychometrics → psychometrics_summary → finances → goals → portfolio → portfolio_review → profile → future
```

Mapping to the API-driven model:

| UI step | What happens | Backend endpoint used |
|---------|--------------|-----------------------|
| `auth` | Register or log in; store `user_id` and `user_name` in Streamlit session state. | `POST /auth/register`, `POST /auth/login` |
| `welcome` | Product explanation and consent. | — |
| `psychometrics` | 18-question behavioural assessment. | `POST /assessments/start`, `POST /assessments/{id}/responses`, `POST /assessments/{id}/complete` |
| `psychometrics_summary` | Review the scored profile and observations. | `GET /users/{id}/profile`, `GET /assessments/{id}/observations` |
| `finances` | Enter income, expenses, liquid savings, optional liabilities. | `PUT /users/{id}/finances` |
| `goals` | Enter one or more goals, or skip. | `POST /users/{id}/goals`, `POST /users/{id}/goals/skip` |
| `portfolio` | Upload a CAS PDF. NSDL/CDSL statements are accepted but stored with parser pending. | `POST /users/{id}/documents?kind=...` |
| `portfolio_review` | Review extracted holdings. | `GET /users/{id}/holdings`, `GET /users/{id}/documents` |
| `profile` | View the Digital Financial Twin. | `GET /users/{id}/twin` |
| `future` | Placeholder for future AI-CIO analysis and decision steps. | — |

## Save / resume semantics

- Each user has exactly one `UserJourney` row (`user_journeys.user_id` is unique).
- `current_step` stores the user's current UI position.
- Per-section statuses are stored in `finances_status`, `goals_status`, and `portfolio_status`.
- Valid status values: `not_started`, `provided`, `skipped`.
- The UI calls `client.set_step(user_id, step)` whenever `go(step)` runs, so progress is persisted to the backend.
- On a new session, the UI could reload the journey via `GET /users/{id}/journey` and resume.

## Skip semantics

- Blank or unknown values are **not** fabricated.
- If a user skips a section, the backend stores an explicit status of `skipped` rather than inventing defaults.
- Skipped sections are surfaced as `unknown` or explicitly marked skipped in the Digital Financial Twin and review output.
- For example, `PUT /users/{id}/finances` with `skipped=true` sets `finances_status = "skipped"` and does not insert cashflows.

## Auth

The journey begins at `auth`. The user can register with name, email, and password, or log in with email and password. The MVP uses PBKDF2-HMAC-SHA256 password hashing; see `privacy-and-security.md` for production caveats.
