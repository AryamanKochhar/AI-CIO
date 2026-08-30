# UI Design Skill — AI-CIO

## Purpose

Guide premium UI work in `apps/web` and `packages/ui`.

## When to use

- New onboarding screens
- Design system additions
- UX copy and empty/error states

## Rules

1. User language, not engineering terms
2. `@ai-cio/ui` for primitives; business logic in feature pages
3. API via `apps/web/src/lib/api.ts` only
4. Blank = unknown, never zero
5. Loading + error on every async screen
6. Financial Map is a Twin projection — never a second financial model

## Visual system

- Font: Inter
- Background: soft slate gradient
- Cards: white, rounded-2xl, subtle shadow
- Primary: slate-900
- Success: emerald; pending: amber

## Definition of done

- Responsive layout
- Accessible labels and focus states
- `pnpm typecheck` + `pnpm build` pass
