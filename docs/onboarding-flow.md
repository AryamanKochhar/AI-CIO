# Onboarding Flow

> Status: **IMPLEMENTED** in `apps/web` and the FastAPI journey API.

## User-facing steps

1. **Sign in** — `/login`
2. **Understand me** — `/onboarding/understand-me`
3. **My finances** — `/onboarding/finances`
4. **My goals** — `/onboarding/goals`
5. **Documents** — `/onboarding/documents`
6. **Review** — `/onboarding/review`
7. **Financial profile** — `/onboarding/twin`

Journey state is persisted via `GET/PUT /users/{id}/journey`.
