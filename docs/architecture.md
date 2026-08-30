# Architecture — AI-CIO

The canonical user journey lives in `apps/web` (Next.js). FastAPI in `apps/api/ai_cio` is the application API. PostgreSQL is the system of record.

```text
apps/web → apps/api/ai_cio/api → apps/api/ai_cio/services → PostgreSQL
```

One `user_id` spans the full onboarding through Digital Financial Twin review.
