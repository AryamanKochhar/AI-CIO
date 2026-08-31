# Financial Map — AI-CIO

> Visual projection of the Digital Financial Twin. Not a second dashboard or data store.

## Purpose

Help users see what AI-CIO understands about their financial life:

WHAT I HAVE → WHERE IT IS → HOW IT IS ALLOCATED → WHAT RELATES TO GOALS → WHAT IS STILL MISSING

## Data source

Built in `ai_cio/services/financial_map.py` and attached to:

```text
GET /users/{id}/twin  →  financial_map
```

Inputs: Twin finances, holdings, goals, liabilities, behaviour, completeness, document provenance.

## Node model

| Type | Meaning |
|------|---------|
| root | Your financial life |
| cash / income / expense | Liquidity and recorded flows |
| investments / asset_class / holding / cluster | Portfolio hierarchy |
| goals / goal | Goals (funding only when user-recorded) |
| liabilities / liability | Debts |

Relationships are containment/inflow/outflow only. **No invented goal↔holding links.**

## Insights

Deterministic rules only (concentration, allocation, liquidity when expenses exist, goal funding when `current_funding` exists, careful behavioural context, data gaps). No LLM. No buy/sell advice.

## UX

- Desktop: zoom/pan canvas, drill-down, breadcrumbs, search, filters, details panel
- Mobile: card list drill-down
- Accessible holdings list remains on the Twin page

## Scalability

Top-N holdings per class (`TOP_N_HOLDINGS = 8`); overflow via cluster “View all N holdings”.

Frontend helpers: search, filters, breadcrumbs (`apps/web/.../map-model.ts`).

## Accessibility

- Desktop canvas is supplemented by mobile list drill-down
- Twin page retains an accessible holdings / transactions list
- Keyboard: Enter opens a branch; breadcrumbs and Up/Reset for orientation

## Future

Same Twin feeds future Specialist Agents / Portfolio Conference — the map stays a human-facing projection.

## Market context

Twin `market_context` adds sector heatmap, breadth, direct equity sector exposure, and deterministic market observations. See `docs/market-intelligence-architecture.md`.
