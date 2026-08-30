# UI Design — AI-CIO

> Premium wealth-management onboarding. Canonical UI: `apps/web`.

## Principles

1. **One journey** — continuous flow, not separate modules
2. **Progressive disclosure** — one question, one financial section at a time
3. **Honest unknowns** — missing data is visible, never fabricated
4. **Provenance** — show where each fact came from
5. **Calm trust** — slate palette, spacious layout, no dashboard clutter

## Component usage

| Screen | Components |
|--------|------------|
| Landing | Hero shell, Card |
| Login | Card, Input, Label |
| Welcome | PageHeader, resume banner |
| Psychometric | ProgressBar, radio-style options |
| Finances | Multi-step ProgressBar |
| Goals | GoalCard grid |
| Documents | FileUploadZone, PortfolioTable |
| Review | ProfileSection, StatusBadge |
| Twin | CompletenessRing, ProfileSection |

## User-facing language

Use "Your Financial Profile" not "Digital Financial Twin" in primary headings.

## States

Every screen implements: loading, error, empty (where applicable), success.

See also: `docs/ui-research.md`, `skills/ui-design.md`.
