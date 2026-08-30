# UI Research — AI-CIO

> Design research for premium wealth-management onboarding. Not proprietary copies.

## Reference products

### Wealthfront / Betterment
- Calm, trust-first visual language
- Progressive onboarding with clear step indicators
- Risk/behaviour questions feel conversational, not clinical
- Portfolio shown only after data exists

### Monarch Money / Copilot Money
- Strong empty states explaining why data is needed
- Document upload with clear processing feedback
- Financial snapshot assembled from user + linked sources
- Human-readable labels, not accounting jargon

## Patterns adopted for AI-CIO

| Pattern | Application |
|---------|-------------|
| Progressive disclosure | One psychometric question; multi-step finances |
| Visible progress | Stepper + “Step X of Y” |
| Trust through provenance | “Source: You provided / CAS / Assessment” |
| Honest unknowns | Missing ≠ zero; explicit “Not provided” |
| Financial map | Hierarchical Twin projection; progressive disclosure; no advice |
| Document state machine | Uploading → Processing → Review → Complete |
| Goal cards | Tap-to-select goal types before details |
| Resume onboarding | “Welcome back — continue where you left off” |

## Visual direction

- **Typography**: Inter, generous line-height, semibold headings
- **Colour**: Slate neutrals, emerald for known/complete, amber for pending
- **Surfaces**: White cards on soft gradient background
- **Density**: Spacious; avoid dashboard clutter
- **Motion**: Minimal; progress bar transitions only

## Anti-patterns avoided

- Giant KPI dashboard on first visit
- Separate “financial map app” or second source of truth
- Exposed module names (Psychometric Engine, Twin Service)
- Raw JSON or parser output
- Stock photo hero imagery
- Clinical psychometric language
- Buy/sell recommendations on the map

## UI/UX Pro Max skill

No dedicated “UI/UX Pro Max” skill was found in the workspace. Design decisions follow `docs/ui-design.md`, `skills/ui-design.md`, `docs/financial-map.md`, and the research above.
