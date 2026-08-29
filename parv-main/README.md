# Investor Behavioral Assessment

## Project Overview

This repository contains a research prototype for an investor psychometric assessment. It asks a user a series of behavioral-finance questions, records the answers and timing information, calculates a behavioral profile, and presents plain-language observations.

The project is intended as an MVP for the AI-CIO project. It is not a clinical psychological test, a financial-advice engine, or a scientifically validated diagnostic instrument. Its scores describe patterns observed from the supplied answers only.

## What Exists Today

- Streamlit frontend for the complete assessment experience.
- FastAPI backend exposing REST endpoints.
- PostgreSQL database running through Docker Compose.
- SQLAlchemy ORM models for users, assessment sessions, responses, and profiles.
- Pydantic schemas for API input and output validation.
- JSON-based question bank containing 18 questions across 7 dimensions.
- Deterministic scoring from 0 to 100.
- Automatic confidence estimation based on question length and response time.
- Profile reliability calculation using confidence, response timing, and confidence consistency.
- Assessment history for the current user.
- Basic admin panel with credential check and system-wide tables/statistics.
- Swagger/OpenAPI documentation supplied automatically by FastAPI.

There is currently no authentication system for normal users, no automated test suite, no migrations, no physiological-data integration, and no financial recommendation functionality.

## Architecture

```text
Browser
  |
  | Streamlit UI (frontend/app.py)
  | HTTP requests using requests
  v
FastAPI API (backend/main.py + backend/routes.py)
  |
  | SQLAlchemy sessions
  v
PostgreSQL (Docker Compose)

Question definitions are loaded locally by the Streamlit frontend
from data/questions.json.
```

The frontend owns page flow and presentation. The backend owns persistence, session validation, profile creation, and API responses. The scoring engine is called by the backend when an assessment is completed.

## Directory and File Guide

### `backend/__init__.py`

Package marker for the backend Python package. It allows imports such as `backend.models` and `backend.routes`.

### `backend/database.py`

Defines the database connection and SQLAlchemy base.

#### `DATABASE_URL`

Reads the database connection string from the environment. The fallback is:

```text
postgresql://postgres:postgres@localhost:5432/psychometric_db
```

When the backend is run inside the Docker network, the hostname is normally `postgres`. When it is run directly on Windows, the hostname normally needs to be `localhost`.

#### `engine`

Creates the SQLAlchemy engine. SQL logging is disabled with `echo=False`. The configured pool permits 10 normal connections and up to 20 additional overflow connections.

#### `SessionLocal`

Session factory bound to the engine. Sessions use `autocommit=False` and `autoflush=False`.

#### `Base`

Declarative base used by all ORM models.

#### `get_db()`

FastAPI dependency that creates one database session per request, yields it to the route, and closes it in `finally` even when the request fails.

#### `init_db()`

Calls `Base.metadata.create_all` to create missing tables when the API starts. This is convenient for the prototype; a production system should use a migration tool such as Alembic.

### `backend/models.py`

Contains the SQLAlchemy database models and relationships.

#### `AssessmentStatus`

String-backed enum with three states:

- `in_progress`: session accepts responses.
- `completed`: profile has been generated.
- `abandoned`: reserved for future abandonment handling.

#### `User`

Maps to `users`.

- `id`: integer primary key.
- `name`: required user name, maximum 255 characters.
- `created_at`: UTC creation timestamp.
- `assessment_sessions`: one-to-many relationship to sessions.

#### `AssessmentSession`

Maps to `assessment_sessions`.

- `id`: integer primary key.
- `user_id`: required foreign key to `users`.
- `started_at`: UTC start timestamp.
- `completed_at`: nullable completion timestamp.
- `status`: `AssessmentStatus`, initially `in_progress`.
- `user`: parent user relationship.
- `responses`: related answers. Deletes cascade from session to responses.
- `profile`: one-to-one profile relationship. Deletes cascade from session to profile.

#### `Response`

Maps to `responses` and stores one submitted answer.

- `id`: integer primary key.
- `session_id`: foreign key to the assessment session.
- `question_id`: question identifier such as `Q001`.
- `answer`: selected answer identifier, such as `1` or `A`.
- `confidence`: integer intended to be between 0 and 100.
- `response_time_ms`: elapsed time for the question.
- `created_at`: UTC creation timestamp.

#### `Profile`

Maps to `profiles`. `session_id` is unique, so each session has at most one profile.

It stores the seven dimension scores, `average_confidence`, `average_response_time_ms`, `profile_confidence`, the related `user_id`, and `created_at`. All score fields are floats intended to use the 0-100 scale.

### `backend/schemas.py`

Contains Pydantic models used to validate request bodies and serialize API responses.

- `UserCreate`: accepts `name` when creating a user.
- `UserResponse`: returns `id`, `name`, and `created_at`. `from_attributes=True` allows serialization from SQLAlchemy objects.
- `AssessmentSessionCreate`: accepts `user_id` when starting a session.
- `AssessmentSessionResponse`: returns session identifiers, timestamps, and status.
- `ResponseCreate`: accepts `question_id`, `answer`, `confidence`, and `response_time_ms`.
- `ResponseModel`: complete response representation, including database ID and timestamp.
- `ProfileResponse`: complete profile representation with all scores and aggregate metrics.
- `AssessmentSummary`: compact history record with session status and optional risk score/profile timestamp.

The schemas currently declare types but do not enforce numeric ranges using Pydantic field constraints. The response route manually checks the confidence range.

### `backend/main.py`

Application entry point.

1. Loads `.env` values through `load_dotenv()`.
2. Calls `init_db()` before serving requests.
3. Creates the FastAPI app with title, description, and version.
4. Enables permissive CORS with all origins, methods, headers, and credentials.
5. Includes the router from `backend.routes`.
6. When executed directly, starts Uvicorn using `API_HOST` and `API_PORT`.

The default direct-run address is `127.0.0.1:8000` unless environment variables change it.

### `backend/routes.py`

Defines the API router and all backend workflows.

#### `health_check()`

`GET /health` returns `{"status": "ok"}`. It is the cheapest endpoint for checking whether FastAPI is reachable.

#### `create_user(user, db)`

`POST /users` creates a `User`, commits it, refreshes it to obtain the generated ID, and returns it through `UserResponse`.

#### `get_user(user_id, db)`

`GET /users/{user_id}` looks up one user. It returns HTTP 404 if the ID does not exist.

#### `start_assessment(session_data, db)`

`POST /assessments/start` first verifies the user, creates an `AssessmentSession` with `in_progress` status, commits it, and returns the new session.

#### `get_assessment(session_id, db)`

`GET /assessments/{session_id}` returns one session or HTTP 404.

#### `submit_response(session_id, response_data, db)`

`POST /assessments/{session_id}/responses` verifies that the session exists and is still `in_progress`, checks confidence is 0-100, stores the answer, and returns the new response ID with `recorded` status.

The route does not currently verify that the question ID exists, that the answer is valid for that question, that a question is answered only once, or that all 18 questions are present before completion.

#### `complete_assessment(session_id, db)`

`POST /assessments/{session_id}/complete` verifies the session state, calls `BehavioralScorer.calculate_profile`, creates a `Profile`, changes the session to `completed`, sets `completed_at`, commits both changes, and returns the profile.

If there are no responses, the scorer raises `ValueError`, which becomes HTTP 400. A completed session cannot be completed again.

#### `get_profile(session_id, db)`

`GET /assessments/{session_id}/profile` returns the saved profile or HTTP 404.

#### `get_observations(session_id, db)`

`GET /assessments/{session_id}/observations` loads the saved profile, builds the score dictionary, calls `BehavioralScorer.generate_observations`, and returns the observation list.

#### `get_user_assessments(user_id, db)`

`GET /users/{user_id}/assessments` verifies the user, loads sessions newest-first, finds each session's profile, and returns compact history records. Incomplete sessions are included with null risk/profile values.

#### `get_admin_stats(db)`

`GET /admin/stats` counts users, all sessions, completed sessions, and calculates in-progress sessions as total sessions minus completed sessions.

#### `get_all_users(db)`

`GET /admin/users` returns all users newest-first.

#### `get_all_assessments(db)`

`GET /admin/assessments` combines each session with its user's name and profile summary. It returns session status, timestamps, risk score, and profile confidence.

The admin API itself has no authentication dependency. The only credential check currently exists in the Streamlit UI, so these endpoints should not be exposed publicly in a production deployment.

### `backend/scoring.py`

Defines `BehavioralScorer`, the deterministic profile calculator.

#### `DIMENSION_QUESTIONS`

Maps questions to dimensions:

| Dimension | Questions |
|---|---|
| Risk tolerance | Q001, Q002, Q015 |
| Loss aversion | Q003, Q004, Q016 |
| Anchoring | Q005, Q006, Q018 |
| Recency bias | Q007, Q008 |
| Herding | Q009, Q010, Q017 |
| Overconfidence | Q011, Q012 |
| Decision stability | Q013, Q014 |

#### `calculate_profile(session_id, db)`

Loads all responses for a session. It rejects an empty response set, calculates all dimension scores, calculates average confidence and response time, calculates profile reliability, and returns the API/profile field names.

#### `_calculate_dimension_scores(responses)`

Filters responses by the mapping above, averages their raw answer values, and normalizes from an assumed 1-5 scale using:

```text
normalized = ((average_raw_score - 1) / 4) * 100
```

Scores are clamped to 0-100 and rounded to one decimal place. A dimension with no response gets a default score of 50.0.

Important current behavior: numeric answer IDs are converted directly to integers. Letter answers use `A=1`, `B=2`, `C=3`, and `D=4`. The function does not read the per-option `score` values in `questions.json`; therefore the JSON score metadata and the scorer can disagree, especially for reverse-scored Likert questions and scenario options. This is a known implementation limitation to explain when describing the current state.

#### `_calculate_average_confidence(responses)`

Returns the arithmetic mean of stored confidence values, rounded to one decimal place, or 0.0 for no responses.

#### `_calculate_average_response_time(responses)`

Returns the arithmetic mean of response times in milliseconds, rounded to one decimal place, or 0.0 for no responses.

#### `_calculate_profile_confidence(responses, avg_confidence)`

Builds a reliability estimate from three signals:

- 55% reported/estimated confidence.
- 25% timing signal. Timing is highest around 20 seconds per question using a Gaussian-like exponential curve.
- 20% confidence consistency. This is `100 - standard_deviation(confidence)` clamped at a minimum of zero.

The final value is clamped to 0-100 and rounded to one decimal place. Negative response times are treated as zero for the timing calculation.

#### `generate_observations(scores)`

Converts score thresholds into natural-language observations. Risk tolerance always gets one interpretation. Other dimensions add observations only for selected high/low thresholds, for example high anchoring, high recency bias, high herding, high overconfidence, or low decision stability. These are descriptive heuristics, not diagnoses.

The current branch rules are:

- Risk tolerance: always reports low preference for stability below 40, moderate tolerance from 40 through 69, or high willingness above or equal to 70.
- Loss aversion: reports defensive positioning at 70 or higher, and opportunistic-buying language below 40. Scores from 40 through 69 add no loss-aversion observation.
- Anchoring: reports possible anchoring at 70 or higher. Lower scores add no anchoring observation.
- Recency bias: reports overweighting recent trends at 70 or higher, or resistance to recent trends below 40.
- Herding: reports crowd-following risk at 70 or higher.
- Overconfidence: reports belief in market-beating ability at 70 or higher, or a cautious view of personal skill below 30.
- Decision stability: reports maintaining conviction at 70 or higher, or adaptability below 40.

The method expects the keys `risk_score`, `loss_aversion_score`, `anchoring_score`, `recency_bias_score`, `herding_score`, `overconfidence_score`, and `decision_stability_score`. A missing key raises `KeyError`; there is no fallback validation inside this method.

### `data/questions.json`

The question bank has version `1.0` and 18 question objects. Each object contains:

- `id`: stable question identifier.
- `type`: `likert` or `scenario`.
- `dimension`: intended behavioral dimension.
- `text`: question shown to the user.
- `options`: answer ID, display text, and intended scoring value.

The questions cover risk tolerance, loss aversion, anchoring, recency bias, herding, overconfidence, and decision stability. Likert questions generally use IDs `1` through `5`; scenario questions generally use letter IDs. Several questions are reverse-scored in the JSON so that a higher intended score represents more adaptive/less biased behavior, depending on the dimension.

The frontend loads this file directly. The backend does not currently load or validate it.

### `frontend/app.py`

This is the Streamlit application. It stores temporary workflow state in `st.session_state` and communicates with FastAPI using the `requests` library.

#### Configuration and styling

The module loads the root `.env`, reads `API_BASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`, configures the Streamlit page, and injects CSS for the light theme, cards, score bars, buttons, hero sections, badges, and animations.

#### `init_session_state()`

Initializes user/session IDs, question position, loaded questions, current page, question timer, profile data, observations, selected answers, and admin authentication. Existing state values are not overwritten.

#### `load_questions()`

Reads `data/questions.json` relative to the frontend file and returns its `questions` list.

#### `calculate_automatic_confidence(question, response_time_ms)`

Estimates confidence from question word count and elapsed time. It computes a target duration between 10 and 45 seconds, combines a timing signal with a completion signal, and returns an integer from 0 to 100. The user does not currently enter confidence manually.

#### API helper functions

Each helper uses the configured `API_BASE_URL`, sends or receives JSON, uses a five-second timeout, calls `raise_for_status()`, and catches `requests.exceptions.RequestException`. Failures are displayed with `st.error()` rather than raised to the page dispatcher.

- `create_user(name)`: sends `POST /users` with the name and returns the created-user JSON or `None`.
- `start_assessment(user_id)`: sends `POST /assessments/start` and returns the created-session JSON or `None`.
- `submit_response(session_id, question_id, answer, confidence, response_time_ms)`: sends one answer to the response endpoint and returns `True` only after a successful request; otherwise returns `False`.
- `complete_assessment(session_id)`: sends the completion request and returns the generated profile JSON or `None`.
- `get_profile(session_id)`: retrieves a saved profile and returns JSON or `None`.
- `get_observations(session_id)`: retrieves generated observations and returns JSON or `None`.
- `get_user_assessments(user_id)`: retrieves history and returns a list; request failures return an empty list.
- `get_admin_stats()`: retrieves aggregate counts and returns JSON or `None`.
- `get_all_users()`: retrieves all users and returns a list; failures return an empty list.
- `get_all_assessments()`: retrieves all assessment summaries and returns a list; failures return an empty list.

#### `score_color(score)`

Chooses the display color: red for 70 or more, amber for 40-69, and green below 40.

#### `render_score_bar(label, score, delay=0)`

Renders a labeled 0-100 score bar with a delayed entrance animation. It ensures the visible bar has at least a small width even when the actual score is zero.

#### `top_nav(active)`

Renders Home, History, and Admin navigation buttons. Clicking a button updates the page in session state and triggers a rerun.

#### `hero(title, subtitle, stats=None)`

Renders the reusable gradient header and optional statistic chips.

When `stats` is supplied, it must be an iterable of `(number, label)` pairs. The values are inserted into HTML and rendered with `unsafe_allow_html=True`, as are several other custom UI fragments in this file.

#### Page functions

- `page_home()`: displays overall statistics, starts an assessment, opens history, describes dimensions, and links to the admin panel.
- `page_name()`: collects a name, creates the user, starts a session, loads questions, resets assessment state, and moves to the assessment page.
- `page_assessment()`: displays one question at a time, tracks elapsed time, stores the selected answer locally, submits it to the backend, and completes the assessment after the final answer.
- `page_results()`: displays aggregate metrics, all seven score bars, generated observations, and navigation to history, a new assessment, or home.
- `page_history()`: retrieves the current user's sessions, renders completed/in-progress status, and loads a selected completed profile back into the results page.
- `page_admin()`: performs the UI-only admin username/password check, displays statistics, lists users, lists assessments, and supports sign out.

#### `main()`

Initializes session state and dispatches to exactly one page function based on `st.session_state.page`. The module calls `main()` when run by Streamlit/Python as the main module.

The valid page values are `home`, `name`, `assessment`, `results`, `history`, and `admin`. There is no default recovery branch for an unknown page value, so an invalid value renders nothing until session state is corrected.

## Function-Level Control Flow

This section summarizes the important side effects that are easy for another AI to miss when reading individual functions.

### Starting an assessment in the frontend

`page_home()` changes only `st.session_state.page` when a button is clicked. `page_name()` performs the actual API work. It strips the submitted name, creates a user, starts a session for that user, loads all questions, resets the question index and selected-answer dictionary, stores the first timer timestamp, and reruns Streamlit. A failed user or session request leaves the user on the name page.

### Answering a question

`page_assessment()` reads the question at `current_question_index`. Option buttons write only the answer ID to `selected_answers` and rerun the page. The answer is not sent to the backend until Submit Answer is clicked. At submission time, the function calculates elapsed milliseconds from `question_start_time`, derives automatic confidence, sends the response, increments the index, resets the timer, and reruns. On the final successful response it immediately calls completion, stores profile JSON, requests observations, changes the page to `results`, and reruns again.

There is no back button, answer editing after submission, pause/resume feature, or frontend recovery flow for a response that was saved successfully but whose subsequent rerun fails.

### Loading results and history

`page_results()` depends on `profile_data` already being present in session state. It does not refetch the profile on every render. `page_history()` refetches the current user's history on each render; selecting a completed item makes two additional requests, for the profile and observations, then places those values in session state before navigating to results.

### Admin UI behavior

`page_admin()` checks the username and password against values loaded from `.env` in the Streamlit process. On success it sets `admin_authenticated=True`. All admin data is then fetched through unauthenticated API endpoints. Signing out clears the flag and returns to home; it does not invalidate any backend session or token because no token exists.

## Important Data Contract

The frontend sends the selected option's `id`, not its `score`. For example, selecting a Likert option sends `"answer": "1"`; selecting a scenario option sends `"answer": "A"`. The `score` property in the question JSON is currently documentation/intended metadata only from the scorer's perspective. The backend stores the answer string exactly as received, and `BehavioralScorer` later converts it using numeric conversion or the A-D fallback map.

The profile response uses API names such as `risk_score` and `profile_confidence`, while the internal dimension map uses names such as `risk_tolerance`. `calculate_profile()` is the translation point between those two naming conventions.

## End-to-End Assessment Flow

1. The home page calls `GET /admin/stats` for headline counts.
2. The user selects Start Assessment and enters a name.
3. The frontend calls `POST /users`.
4. The frontend calls `POST /assessments/start` for the new user.
5. Questions are loaded locally from `data/questions.json`.
6. For each question, the UI starts a timer, shows the options, and stores the selected option in session state.
7. On submission, the frontend calculates automatic confidence and elapsed milliseconds.
8. The frontend sends the answer to `POST /assessments/{session_id}/responses`.
9. After the last answer, the frontend calls `POST /assessments/{session_id}/complete`.
10. The backend loads responses and creates the profile through `BehavioralScorer`.
11. The frontend requests observations through `GET /assessments/{session_id}/observations`.
12. The results page displays scores, reliability metrics, and textual observations.

## Scoring Interpretation

The display uses three broad bands:

- `0-39`: lower measured tendency.
- `40-69`: moderate measured tendency.
- `70-100`: higher measured tendency.

The meaning of a high score depends on the dimension. For example, a high risk score means greater willingness to accept volatility, while a high loss-aversion score is intended to indicate higher sensitivity to losses. Because the current scorer uses answer IDs rather than JSON option scores, these interpretations should be treated as prototype behavior until scoring is aligned with the question metadata.

## Environment Variables

Typical root `.env` values are:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/psychometric_db
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://127.0.0.1:8000
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
```

Use `postgres` as the database hostname from a Docker container and `localhost` when the Python backend runs directly on the host machine.

## Installation and Running

### Prerequisites

- Python 3.8 or newer.
- Docker Desktop with Docker Compose.
- PowerShell or Command Prompt on Windows.

### Manual setup

```powershell
cd d:\parv\psychometric
docker-compose up -d
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the backend in one terminal:

```powershell
cd d:\parv\psychometric\backend
python main.py
```

Run the frontend in another terminal:

```powershell
cd d:\parv\psychometric\frontend
streamlit run app.py
```

Open:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Streamlit: `http://localhost:8501`

### Startup scripts

- `start.ps1` checks Docker, starts PostgreSQL, activates the virtual environment, and prints the commands needed to run backend and frontend.
- `start.bat` provides the equivalent Command Prompt-oriented launcher.

Neither script starts FastAPI or Streamlit automatically; they prepare the environment and show the next commands.

## Docker and Dependencies

### `docker-compose.yml`

Runs PostgreSQL 15 Alpine as service `postgres`, exposes port 5432, creates database `psychometric_db`, persists data in the `postgres_data` named volume, and uses `pg_isready` as a health check.

### `requirements.txt`

- `fastapi`: API framework.
- `uvicorn`: ASGI server.
- `sqlalchemy`: ORM and database sessions.
- `psycopg2-binary`: PostgreSQL driver.
- `pydantic` and `pydantic-settings`: validation/configuration support.
- `python-dotenv`: `.env` loading.
- `streamlit`: frontend framework.
- `requests`: frontend-to-backend HTTP client.

## API Quick Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health check |
| POST | `/users` | Create a user |
| GET | `/users/{user_id}` | Get one user |
| POST | `/assessments/start` | Start a session |
| GET | `/assessments/{session_id}` | Get session details |
| POST | `/assessments/{session_id}/responses` | Save one answer |
| POST | `/assessments/{session_id}/complete` | Score and complete session |
| GET | `/assessments/{session_id}/profile` | Get saved profile |
| GET | `/assessments/{session_id}/observations` | Get generated observations |
| GET | `/users/{user_id}/assessments` | Get user history |
| GET | `/admin/stats` | Get counts |
| GET | `/admin/users` | List users |
| GET | `/admin/assessments` | List sessions and summaries |

## Database Lifecycle

Tables are created on FastAPI startup. Data remains in the Docker named volume while the containers are stopped. `docker-compose down` stops and removes containers but keeps the named volume. `docker-compose down -v` also removes the volume and therefore deletes the local PostgreSQL data; use that only when intentionally resetting the prototype database.

## Current Limitations and Technical Debt

1. No real user authentication or authorization.
2. Admin credentials are a frontend-only comparison and default to `admin/admin` if not configured.
3. CORS allows every origin and credentials.
4. API inputs do not validate question IDs, answer IDs, duplicate answers, or completion count.
5. The scorer ignores the JSON option `score` values and uses answer IDs instead.
6. No database migrations or automated tests exist.
7. History performs separate profile/user queries and may need optimized joins at scale.
8. Assessment abandonment is represented in the enum but not implemented in the UI/API.
9. The question bank is loaded by the frontend rather than served/versioned by the backend.
10. Confidence is an automatic timing heuristic, not a validated measurement of psychological confidence.
11. Scores and observations are research outputs and must not be presented as financial advice or psychological diagnoses.

## Suggested Next Development Steps

- Make the backend load the question bank and validate every question/answer.
- Score using each option's explicit JSON `score` value.
- Add Pydantic range constraints and database check constraints.
- Prevent duplicate responses and require the expected question set before completion.
- Add Alembic migrations and pytest coverage for scoring and routes.
- Replace UI-only admin protection with server-side authentication and authorization.
- Add structured logging, request IDs, and production CORS configuration.
- Add profile visualizations and longitudinal comparisons.
- Add optional physiological or hardware data only after defining consent, privacy, and data-retention rules.

## AI Handoff Summary

Use the following description when explaining the project to another AI:

> I built a Python research prototype for an investor behavioral assessment. The Streamlit frontend in `frontend/app.py` manages a multi-page questionnaire, creates users and assessment sessions through a FastAPI backend, times each answer, estimates confidence automatically, submits responses, and displays results. The FastAPI backend in `backend/main.py` and `backend/routes.py` exposes health, user, assessment, response, profile, history, and admin endpoints. PostgreSQL runs through `docker-compose.yml`, and SQLAlchemy models in `backend/models.py` persist users, sessions, responses, and one profile per completed session. Pydantic models in `backend/schemas.py` define API payloads. Questions are stored in `data/questions.json` and cover seven dimensions: risk tolerance, loss aversion, anchoring, recency bias, herding, overconfidence, and decision stability. `backend/scoring.py` calculates normalized 0-100 dimension scores, average confidence, average response time, profile reliability, and textual observations. The current prototype has no real authentication, tests, migrations, or financial recommendations. A key scoring limitation is that the scorer currently interprets answer IDs directly and does not yet use the explicit per-option JSON score values.

## Version

Prototype version: `0.1.0`
