---
name: nism-investment-adviser-l2
description: >-
  Apply NISM Series X-B Investment Adviser (Level 2) concepts for insurance,
  retirement products, Indian taxation of securities, estate planning,
  behavioural finance, and risk profiling. Use when AI-CIO touches insurance
  needs, tax education, estate/will tools, risk profiles, product comparison,
  case-based advice UX, or when the user mentions NISM X-B / Level 2.
---

# NISM Investment Adviser Level 2

Source workbook: `docs/books/NISM Series-X-B_Investment Adviser Level 2.pdf`.

Complements Level 1 for SEBI Investment Adviser certification. **Not investment advice.** Use for structured education and suitability framing inside AI-CIO.

## When to use

- Insurance planning vs investment confusion (ULIP vs term + invest)
- Retirement products and adviser role (cross-check NPS skill for depth)
- Tax concepts for debt/equity/other products (educational, not tax advice)
- Estate planning basics and tools (will, nomination, trust — high-level)
- Behavioural finance biases and risk profiling UX
- Cross-category product comparison and case-study style flows

## Knowledge map (20 chapters)

| Module | Chapters | Agent focus |
|--------|----------|-------------|
| Insurance | 1–3 | Risk management, life vs non-life, product features; insurance ≠ investment |
| Retirement | 4–6 | Retirement basics, products, miscellaneous aspects |
| Taxation | 7–13 | Tax concepts, capital gains, other sources, debt/equity/other products, special cases |
| Estate | 14–15 | Estate planning basics and tools |
| Behaviour & advice | 16–20 | Behavioural finance, risk profiling, product comparison, case studies |

## Hard rules for AI-CIO

1. **Insurance first principle** — protection need before investment wrapper; do not sell ULIPs as “superior equity”.
2. **Tax is educational** — cite concepts (STCG/LTCG, holding periods, product tax treatment) as general knowledge; never give personalized tax opinions or filing instructions.
3. **Estate tools are sensitive** — describe wills, nominations, joint holding, trusts at concept level; urge professional counsel for drafting.
4. **Risk profiling is mandatory framing** — risk capacity (ability) ≠ risk attitude (willingness) ≠ need; never map a quiz score straight to a product ticker.
5. **Behavioural finance** — name biases (loss aversion, overconfidence, mental accounting, herd) to *explain* user patterns; do not shame or override user goals.
6. **Product comparison** — compare on risk, liquidity, horizon, tax *treatment class*, costs, and fit — not on “best performer”.
7. **Case studies** — use structured steps: facts → goals → constraints → gaps → options to *review* → disclaimer.
8. **No autonomous trades** — L2 knowledge never authorizes trade execution.

## Risk-profiling checklist

When designing or reviewing profiling UX:

- [ ] Separates capacity, attitude, and need
- [ ] Captures horizon, liquidity, dependents, income stability
- [ ] Allows “unknown / incomplete” without forcing a bucket
- [ ] Links profile to *allocation education*, not stock picks
- [ ] Surfaces conflicts (e.g. high need for return + low capacity)

## Output pattern for case-style responses

```
1. Client situation (only known facts)
2. Goals & constraints
3. Gaps / risks observed
4. Concepts / product *categories* to review
5. Open questions / missing data
6. Disclaimer (not advice; not tax opinion)
```

## Do NOT

- Recommend specific insurance policies, funds, or stocks
- Assert exact tax payable for a user
- Treat behavioural labels as clinical diagnoses
- Collapse L1 + L2 into a single “just invest more” narrative

## Related

- Foundations: skill `nism-investment-adviser-l1`
- Retirement depth (NPS/PFRDA): skill `nism-retirement-adviser`
- Money behaviour stories: skill `psychology-of-money`
- Psychometric product work: `skills/psychometric-development.md`
