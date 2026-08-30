# Skill: UI Development

## Purpose

Change the Streamlit UI (`frontend/app.py` and supporting pages) while keeping the UI a thin client over the FastAPI backend, preserving the single unified journey and honest handling of unknowns.

## When to use

- Adding or changing screens in the onboarding journey.
- Updating forms for psychometrics, finances, goals, or portfolio upload.
- Improving error states, loading states, or empty states.
- Changing navigation, progress tracking, or decision capture.

## Architectural constraints

- The UI is a **thin HTTP client** over FastAPI.
- All API calls go through `frontend/client.py`.
- No business logic, validation rules, or scoring in the UI.
- No direct database access from the UI.
- One unified journey: Welcome → Psychometrics → Finances → Goals → Portfolio → Review → Analysis → Decide.
- Unknown data stays unknown; the UI must not invent placeholder values.
- Errors are surfaced to the user in friendly language, not raw stack traces.

## Files to inspect first

1. `frontend/app.py` — main Streamlit journey.
2. `frontend/client.py` — HTTP client and `ApiError`.
3. `ai_cio/api/routes.py` — routes the UI can call.
4. `ai_cio/api/schemas.py` — request/response shapes.
5. `ai_cio/services/journey.py` — onboarding status and step management.
6. `docs/current-architecture.md` — current UI flow and gaps.

## Implementation rules

1. **Call API through `frontend/client.py` only**: every backend interaction uses the helpers in `client.py`. Use `ApiError` for failures.
2. **No business logic in the UI**:
   - Do not compute scores, net worth, allocations, or tax estimates.
   - Do not validate beyond lightweight form-level checks (required fields, numeric parse).
   - Do not branch on domain state that should live in services.
3. **No direct DB**: the UI must never import `ai_cio/db` modules or construct SQLAlchemy sessions.
4. **Single unified journey**: do not create new dashboards or parallel entry points. Keep users inside the canonical journey.
5. **Unknown stays unknown**: display missing values as "Unknown", "Not provided", or leave blank. Never fabricate sample numbers.
6. **Friendly errors**: catch `ApiError` and connection errors; show a clear message and, if appropriate, a retry path. Do not show raw tracebacks.
7. **Session state only for UI state**: store `user_id`, `session_id`, current step, and transient form values in `st.session_state`. Do not cache domain objects longer than a screen transition.
8. **Progress and status**: read journey status from the API and reflect it; do not duplicate status logic.
9. **Accessibility and readability**: use clear labels, group related fields, and provide help text for financial jargon.
10. **Style consistency**: prefer reusable helpers and constants; avoid scattering inline CSS. The project does not yet have a design system, so keep additions minimal and consistent.

## Testing requirements

- Manual smoke test: run `streamlit run frontend/app.py` and walk through the affected screens.
- If the change touches `frontend/client.py`, add or update tests that mock the API responses.
- Run `pytest -q` before finishing to ensure no backend regressions.

## Do NOT

- Implement scoring, parsing, or financial calculations in the UI.
- Access the database directly.
- Create new Streamlit entry points or dashboards outside the unified journey.
- Fabricate placeholder data to make screens look complete.
- Expose raw API error details to end users.
- Import from `ai_cio/services/` or `ai_cio/db/` in frontend code.

## Definition of done

- [ ] UI changes use `frontend/client.py` for all backend calls.
- [ ] No business logic or scoring added to the UI.
- [ ] Unknown values are displayed honestly.
- [ ] Errors are handled with friendly messages.
- [ ] Journey remains unified; no new dashboards created.
- [ ] Smoke-tested in Streamlit for the affected screens.
- [ ] `pytest -q` passes.
