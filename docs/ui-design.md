# UI Design — AI-CIO

> Status: **IMPLEMENTED** for the Next.js web application (`apps/web`).

## Design intent

AI-CIO should feel like **private wealth management with an intelligent assistant** — calm, trustworthy, minimal, and financially literate without exposing engineering terminology.

## Inspiration principles (not copied layouts)

Extracted from products such as Wealthfront, Betterment, Monarch Money, and Copilot Money:

- Progressive disclosure — one question or section at a time
- Guided onboarding with visible progress
- Excellent empty states that explain what happens next
- Simple forms with optional fields clearly marked
- Document upload with explicit processing states
- Understandable charts and tables (when data exists)
- Strong confirmation states after each step

## Visual language

| Token | Value |
|-------|-------|
| Background | Soft slate gradient (`#f8fafc` → `#eef2f7`) |
| Primary surface | White cards with subtle border (`slate-200`) |
| Hero / brand shell | Deep slate (`slate-900`) |
| Typography | Inter, semibold headings, relaxed body copy |
| Border radius | `rounded-lg` inputs, `rounded-2xl` cards |
| Accent | Slate-900 buttons; no loud gradients |

## Component system

Shared primitives live in `packages/ui/`:

- `Button`, `Input`, `Label`, `Card`
- `ProgressBar`, `Stepper`
- `EmptyState`, `StatusBadge`, `PageHeader`

Business logic and journeys live in `apps/web/src/features/` and route pages under `apps/web/src/app/onboarding/`.

## User-facing language

| Show | Do not show |
|------|-------------|
| Understand me | Psychometric Engine |
| My finances | Data Processing Engine |
| My goals | Goal subsystem |
| Add your financial documents | CAS Parser |
| Your Financial Profile | Digital Twin JSON |
| Review | Portfolio Conference |

## Document upload UX

States communicated to the user:

1. **Uploading** — file selected, request in flight
2. **Processing / Extracting** — CAS parser running
3. **Review** — warnings present, holdings need confirmation
4. **Complete** — holdings available
5. **Pending** — NSDL/CDSL stored, parser not yet supported
6. **Failed** — human-readable error, no stack traces

## Accessibility

- Sufficient colour contrast on text and buttons
- Focus rings on interactive elements
- Form labels associated with inputs
- Progress communicated visually and in text

## Responsive behaviour

- Single-column forms on mobile
- Stepper wraps on narrow screens
- Tables scroll horizontally when needed

## PLANNED (not yet implemented)

- Dark mode
- Rich portfolio allocation charts
- Animated micro-interactions
- Full design tokens package export for Figma
