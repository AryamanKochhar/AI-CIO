---
name: canslim-strict-mode
description: >-
  Apply CANSLIM Strict Mode theory — Dow/Livermore/Wyckoff/O'Neil lineage,
  market psychology, and the seven CANSLIM letters as a conjunction filter —
  when designing or reviewing breakout screening, relative strength, bases,
  pivots, market-direction gates, or momentum opportunity detection. Use when
  the user mentions CANSLIM, Strict Mode, O'Neil, VCP, breakouts, or IBD-style
  leadership screens.
---

# CANSLIM Strict Mode

Source: `docs/books/CANSLIM Strict Mode Handbook COMPLETE.pdf` (ORBIX Volume I — Theory & Lineage).

Engineering textbook for a disciplined breakout screening system. **Educational / system-design only — not investment advice.** AI-CIO may use these ideas for *detection and explanation of market structure*, never for autonomous trade instructions.

## When to use

- Opportunity / leadership / breakout detection design
- Explaining why a name screened in or out
- Market-direction (index) gates and regime filters
- Base / pivot / relative-strength concepts in code or docs
- Reviewing momentum features against first-principles filters

## Organising chain

Every filter must be traceable:

```
Market psychology → Historical origin → Financial theory → Quant evidence
  → Engineering implementation → Code → Product / practice
```

If a chapter or feature cannot walk this chain, it is decoration — drop or quarantine it.

## Three sub-problems (lineage)

| Problem | Question | Lineage anchors |
|---------|----------|-----------------|
| Detection | Fingerprint of informed buying? | Dow phases, Wyckoff accumulation, bases |
| Timing | When to commit? | Livermore pivot, O'Neil breakout, Minervini contraction |
| Survival | Stay solvent when most fail? | Cut losers, stage analysis, market veto (M) |

## CANSLIM as three questions

| Bucket | Letters | Question |
|--------|---------|----------|
| Fundamental fuel | **C**, **A** | Should this company reprice up? |
| Character / demand | **N**, **S**, **L**, **I** | Is smart money accumulating *now*? |
| Timing / market | **M** | Is the tide with me? (~3 of 4 stocks follow the index) |

### Letter meanings (Strict Mode reading)

- **C** — Current quarterly earnings: large *accelerating* EPS vs year-ago; surprise > steady growth
- **A** — Annual earnings + high ROE: durable trajectory, not a one-quarter bounce
- **N** — New: new product/management/condition *and* new high out of a base
- **S** — Supply & demand: float tightness + demand surge (volume); pair with liquidity floor
- **L** — Leader not laggard: relative strength; forbid “cheap laggard” catch-up trades
- **I** — Institutional sponsorship: rising quality ownership; avoid over-owned late stage; OBV/volume as proxy when holdings stale
- **M** — Market direction: **veto** over everything left; refuse breakouts in hostile tape

### Central rule

Edge is the **conjunction**, not cherry-picked letters. “Strict” means no discretionary exceptions under emotional pressure.

## Engine seam (AI-CIO)

| Native to price/volume engine | Needs fundamental data upstream |
|------------------------------|----------------------------------|
| N (highs/bases), S (volume/liquidity), L (RS), part of I (accumulation proxies), M (index) | C, A (earnings/ROE gates) |

Keep the seam clean for determinism and replay. Do not invent earnings prints.

## Product rules for AI-CIO

1. Screen results are **observations / candidates for review**, never buy orders.
2. Always show **market regime (M)** alongside any leadership list.
3. Missing C/A data → mark fundamental gates unknown; do not fake them.
4. Prefer deterministic filters over LLM “gut feel” ranking.
5. Document failure regimes (momentum crashes, Stage-4 markets) when exposing screens.

## Do NOT

- Emit buy/sell instructions from CANSLIM matches
- Treat U.S. 1980s O'Neil thresholds as laws for Indian equities without re-validation
- Drop M “just this once”
- Fabricate Strict Mode code parameters not present in the repo

## Related

- Market opportunity architecture: `docs/opportunity-detection.md`, `docs/market-intelligence-architecture.md`
- Analysis contract: `skills/financial-analysis.md`
- Tone / disclosures: `skills/financial-explainability.md`
