# Opportunity Detection — AI-CIO

Deterministic rules only. **Opportunity ≠ recommendation.**

## Pipeline

```text
Market event + portfolio exposure + Twin context + rules → OpportunityCandidate
```

## Configurable thresholds (`.env`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPPORTUNITY_SECTOR_CHANGE_THRESHOLD` | 3.0 | \|sector daily %\| |
| `OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD` | 2.0 | \|relative to benchmark\| (pp) |
| `OPPORTUNITY_EXPOSURE_THRESHOLD_PCT` | 5.0 | Min equity weight % |

A candidate requires **at least two** reason codes (e.g. sector move + material exposure).

## Severity

- `attention` — sector decline with exposure
- `information` — other material moves

## Output

Stored in `market_opportunities` with `reason_json` for auditability.

## Idempotency

`POST /users/{id}/market/process` fingerprints each observation (type, sector, moves, exposure) per calendar day. Repeated calls on the same day do not duplicate alerts/emails.

## Downstream

Qualified candidates flow to sanitized Twin context → LiteLLM (optional) → email. See `docs/litellm-integration.md`.
