# UI Development — AI-CIO

## Purpose

Change the Next.js UI in `apps/web` while keeping it a thin client over the FastAPI backend.

## When to use

- Adding or changing onboarding screens
- Updating the design system in `packages/ui`
- Connecting new API endpoints from the frontend

## Rules

1. All API calls go through `apps/web/src/lib/api.ts`
2. Business logic stays on the backend — no psychometric scoring or money calculations in the browser
3. Use user-facing language ("Understand me", not "Psychometric Engine")
4. Blank fields mean **unknown**, not zero

## Definition of done

- [ ] Uses `@ai-cio/ui` components where possible
- [ ] API types from `@ai-cio/contracts`
- [ ] `pnpm typecheck` and `pnpm build` pass
- [ ] Manual smoke test of affected route
