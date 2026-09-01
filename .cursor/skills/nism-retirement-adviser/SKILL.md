---
name: nism-retirement-adviser
description: >-
  Apply NISM Series XVII Retirement Adviser concepts for retirement goals,
  NPS, fund evaluation, retirement strategies, special situations, and PFRDA
  regulations. Use when AI-CIO builds retirement planning, NPS education,
  corpus/gap analysis, drawdown concepts, or when the user mentions NISM XVII,
  PFRDA, or Retirement Adviser.
---

# NISM Retirement Adviser (Series XVII)

Source workbook: `docs/books/NISM Series XVII Retirement Adviser Certification Examination - July 2026.pdf` (July 2026 edition).

Benchmark knowledge for PFRDA (Retirement Adviser) Regulations, 2016. **Not retirement or investment advice.**

## When to use

- Retirement goal framing (corpus, inflation, longevity, healthcare)
- NPS structure, benefits, and fund selection education
- Other retirement products and strategy education
- Special situations (early retirement, job change, longevity risk)
- Regulatory / adviser-conduct framing for retirement features

## Knowledge map (9 units)

| Unit | Topic | Weight (exam) | Agent focus |
|------|-------|---------------|-------------|
| 1 | Fundamental concepts | — | Need, TVM for retirement, start-early, underestimation risk, emotions |
| 2 | Markets & investment products | 10% | Product map for accumulation |
| 3 | Retirement planning process | 15% | Process steps, gap analysis |
| 4 | NPS | — | Architecture, tiers, choices, benefits |
| 5 | Fund performance & selection | — | Evaluation tools (not fund picks) |
| 6 | Other investment products | — | Non-NPS retirement vehicles (education) |
| 7 | Strategies | 12% | Accumulation / transition / decumulation concepts |
| 8 | Special situations | 10% | Edge cases and adjustments |
| 9 | Regulations & regulators | 10% | PFRDA / adviser conduct |

## Hard rules for AI-CIO

1. **Retirement is a goal, not a product** — start from lifestyle need, horizon, and inflation; products follow education.
2. **Start-early compounding** — teach the concept; never promise a future corpus number unless formula inputs are user-supplied and shown.
3. **Underestimation risk** — call out longevity, healthcare, inflation; do not soft-pedal shortfalls when Twin data shows them.
4. **NPS education** — explain tiers, asset classes, lifecycle vs active choice as *mechanics*; do not recommend a specific pension fund manager.
5. **Fund evaluation** — discuss metrics (risk-adjusted return concepts, consistency, costs) as criteria; never crown a “best fund”.
6. **Strategies** — accumulation vs decumulation; sequence-of-returns risk as education; no withdrawal-rate guarantees.
7. **Special situations** — list considerations; require missing-data questions before conclusions.
8. **Regulatory** — retirement-adviser conduct is constrained; AI-CIO must not pose as a registered Retirement Adviser unless product explicitly is.

## Gap-analysis pattern

```
Required corpus (stated or calculated with shown inputs)
− Current retirement assets (Twin facts only)
− Expected contributions (user-stated)
= Gap / surplus (label confidence; mark unknowns)
Next step: what to review — not what to buy
```

## Do NOT

- Recommend specific NPS fund managers or schemes as “best”
- Guarantee replacement ratios or safe withdrawal rates
- Ignore inflation / longevity when projecting
- Invent employer benefits (EPF/gratuity) not present in Twin

## Related

- Broader adviser L2 retirement chapters: skill `nism-investment-adviser-l2`
- Behaviour / “never enough”: skill `psychology-of-money`
- Twin / financial map: `docs/financial-map.md`, `docs/digital-financial-twin.md`
