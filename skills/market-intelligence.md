# Market Intelligence Skill — AI-CIO

## Purpose

Connect **market events** with **user Twin state** using deterministic analytics first.

## Allowed

- Fetch NSE via `NSEProvider`
- Persist snapshots to PostgreSQL
- Calculate relative performance, breadth, exposure weights
- Classify securities from NSE sector constituents
- Detect opportunity candidates with configured thresholds
- Retrieve `knowledge/` passages
- Optional LiteLLM structured explanation (`docs/litellm-integration.md`)
- Send observation emails (not trade tips)

## Forbidden

- Frontend → NSE direct calls
- LLM calculating percentages or fetching market data
- Guessing sectors from names
- MF look-through without fund holdings data
- Buy/sell instructions in this tranche

## Twin rule

User financial state always comes from Twin assembly — never a parallel model.
