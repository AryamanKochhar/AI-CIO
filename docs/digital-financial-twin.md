# Digital Financial Twin — AI-CIO

> Status: **IMPLEMENTED** via `GET /users/{id}/twin` in `ai_cio/services/twin.py`.

## What it is

The Digital Financial Twin is an **assembled, read-only representation** of a user's current financial state. It is **not** a second database. It is built on demand from the canonical PostgreSQL records.

## Endpoint

```text
GET /users/{id}/twin
```

## What it includes

- **User**: id and name, marked as user-provided.
- **Behaviour**: latest completed psychometric profile with explicit provenance (session id, instrument id, instrument version).
- **Financial position**: income, expenses, liquid, liabilities, and a system-calculated net worth.
- **Portfolio**: document count, holdings count, total value, and up to 12 CAS-derived holdings.
- **Goals**: list of user-provided goals.
- **Completeness map**: boolean flags for `psychometric`, `income`, `expenses`, `liquid`, `liabilities`, `goals`, `portfolio`, `horizon`.
- **Dimension labels**: what higher scores mean for each psychometric dimension.
- **ready_for_analysis**: true only when `psychometric`, `income`, `expenses`, `liquid`, `goals`, and `portfolio` are all known.

## Provenance

Every important fact carries an explicit source tag:

| Source | Meaning |
|--------|---------|
| `user-provided` | Entered by the user in the UI. |
| `cas-derived` | Extracted from an uploaded CAS PDF. |
| `system-calculated` | Computed by the backend (e.g., net worth). |
| `psychometric_assessment` | Comes from a completed psychometric session; includes session and instrument provenance. |

## No fabricated values

- Missing facts are returned as `null` or marked `unknown`.
- The Twin does not invent income, expenses, liquid, holdings, or goals.
- `ready_for_analysis` is intentionally strict; it is false if any core section is missing.

## Net worth calculation

```text
net_worth = liquid + portfolio_value - total_liability_balance
```

If `liquid` or `portfolio_value` is missing, that component is treated as 0 for the calculation, but the corresponding `known` flag stays false.

## Planned (not implemented)

- Corrections workflow for CAS-derived facts.
- Explicit constraint records used in analysis.
- Market data refresh for current valuations.
- Twin versioning or snapshots.
