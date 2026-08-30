# User Journey — AI-CIO

> Canonical flow in `apps/web`.

```text
/                     Landing
/login                Register or sign in
/onboarding/welcome   Introduction + resume
/onboarding/understand-me   Psychometric (18 questions)
/onboarding/finances        Progressive financial profile
/onboarding/goals           Goal cards + CRUD
/onboarding/documents       Upload + portfolio review
/onboarding/review          Summary before profile
/onboarding/twin            Your Financial Profile (Digital Twin + Financial Map)
```

The Twin page includes an interactive **Financial Map** — a visual projection of the same Twin data (drill-down, search, insights). Not a separate product.

Journey state persisted via `GET/PUT /users/{id}/journey`.

Resume on login routes to last `current_step`.
