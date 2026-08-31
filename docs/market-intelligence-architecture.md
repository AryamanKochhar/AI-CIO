# Market Intelligence Architecture — AI-CIO

> Market data is external context. The Digital Financial Twin remains the single source of truth for user financial state.

## Current state (implemented)

- NSE provider, analytics, sector exposure, opportunity detection
- Twin `market_context` + Financial Map `MarketContextPanel`
- LiteLLM optional analysis via `LiteLLMProvider` (external gateway)
- Sanitized Twin context before LLM (`twin_context_builder.py`)
- Idempotent opportunity processing (fingerprint per day)
- See `docs/litellm-integration.md`

## Proposed architecture

```text
NSE (heatmap + sector indices)
        ↓
NSEProvider (session, retry, cache)
        ↓
Normalized MarketIndexSnapshot
        ↓
PostgreSQL (market_indices, market_index_snapshots)
        ↓
MarketAnalyticsService (deterministic)
        ↓
Security classification (NSE sector constituents → securities)
        ↓
User sector exposure (direct equity only; MF look-through future)
        ↓
Digital Financial Twin (+ market_context)
        ↓
OpportunityCandidate (rules, configurable thresholds)
        ↓
Knowledge retriever (authoritative markdown)
        ↓
LiteLLMProvider (optional structured analysis)
        ↓
Email notification (log/SMTP)
```

## Data sources

| Source | Use |
|--------|-----|
| NSE heatmap `Broad Market Indices` | Benchmark (Nifty 50, etc.) |
| NSE heatmap `Sectoral Indices` or `equity-stockIndices` | Sector performance |
| NSE sector index constituents | ISIN/symbol → sector classification |

Documented in `docs/market-data-sources.md`.

## Storage

- `market_indices` — canonical index registry
- `market_index_snapshots` — time-series snapshots (deduped by index + timestamp)
- `securities` — classification master (unknown when not mapped)
- `market_opportunities`, `market_opportunity_analyses`, `user_alerts`, `notification_deliveries`

## Twin integration

Twin response includes `market_context`:

- benchmark move, sector heatmap rows, breadth
- user `sector_exposure` (direct equity)
- deterministic `observations` (not recommendations)

Market failures do **not** break Twin assembly.

## LiteLLM role

- Interprets supplied facts only when `LLM_ENABLED=true`
- Never fetches NSE, never calculates weights, never queries DB
- Falls back to deterministic analysis when disabled or on failure

## Limitations (this tranche)

- No mutual fund sector look-through
- No buy/sell recommendations
- No regulatory suitability claims
- Sector unknown when ISIN not in classification master

## Future evolution

Specialist agents and Portfolio Conference consume the same Twin + market contracts.
