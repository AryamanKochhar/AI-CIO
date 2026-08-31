# Financial Analysis Skill — AI-CIO

Use when interpreting portfolio and market facts for users or LLM prompts.

## Principles

1. **Deterministic backend is source of numerical truth** — weights, exposures, sector moves come from NSE + Twin calculations.
2. **LLM interprets; it does not calculate** — never ask the model to derive percentages or invent holdings.
3. **Observation, not recommendation** — surface material moves and concentration; do not say buy/sell/guaranteed.
4. **Knowledge is interpretive** — cite NISM/SEBI/NSE for concepts (diversification, horizon, rebalancing), not product picks.

## Analysis contract

Output shape: `MarketOpportunityAnalysis` in `apps/api/domain/market/contracts.py`.

Required fields: `summary`, `why_relevant`, `confidence`, `recommended_next_step`.

## Context assembly

Use `build_sanitized_analysis_context()` — never `json.dumps(twin)`.

Include: market facts (source, as-of, freshness), portfolio exposure for relevant sector, goals/horizon when known, completeness gaps.

Exclude: PAN, Aadhaar, raw CAS, credentials.

## Failure handling

On LLM failure, use `DeterministicLLMProvider` fallback. Retain the opportunity record; mark analysis source accordingly.

## Related docs

- `docs/litellm-integration.md`
- `docs/market-intelligence-architecture.md`
- `docs/opportunity-detection.md`
