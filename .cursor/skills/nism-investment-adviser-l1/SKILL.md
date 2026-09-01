---
name: nism-investment-adviser-l1
description: >-
  Apply NISM Series X-A Investment Adviser (Level 1) concepts for personal
  financial planning, Indian markets, products, portfolio construction, SEBI
  regulations, and adviser ethics. Use when building or reviewing AI-CIO advice
  flows, financial planning logic, product education, portfolio construction,
  compliance copy, or when the user mentions NISM X-A / Level 1.
---

# NISM Investment Adviser Level 1

Source workbook: `docs/books/14 NISM-Series-X-A Investment Adviser (Level 1) - March 2026_.pdf` (March 2026 edition).

Educational / regulatory knowledge for Indian investment advisers under SEBI (Investment Advisers) Regulations, 2013. **Not investment advice.** Align AI-CIO language with observation + education, never buy/sell instructions.

## When to use

- Personal financial planning, net worth, cash flow, debt, TVM
- Explaining Indian financial markets / securities segments
- Equity, debt, derivatives, mutual funds, PMS, AIF education
- Portfolio construction, MPT basics, performance evaluation
- Operational / regulatory / ethics / grievance-redress copy

## Knowledge map (20 chapters)

| Module | Chapters | Agent focus |
|--------|----------|-------------|
| Personal financial planning | 1–4 | Goals, assets/liabilities/net worth, planning process, TVM, cash flow/budget, debt & loans |
| Indian markets | 5–6 | Market structure, primary/secondary segments |
| Investment products | 7–13 | Stocks, fixed income, derivatives, MFs, PMS, AIFs |
| Portfolio | 14–16 | MPT, construction process, performance measurement |
| Ops & compliance | 17–20 | Operations, key regulations, ethics, grievance redress |

## Hard rules for AI-CIO

1. **Suitability before products** — frame goals, horizon, liquidity, risk capacity before any product discussion.
2. **Net worth language** — Assets − Liabilities = Net worth; never invent client numbers; only use Twin/CAS facts.
3. **TVM is math, not a pitch** — PV/FV/annuity explanations are educational; do not imply guaranteed returns.
4. **Product education ≠ recommendation** — describe categories (equity/debt/MF/PMS/AIF); never “buy X” or “switch to Y”.
5. **Derivatives = risk tools** — emphasize leverage, margin, and loss potential; never present as income strategies.
6. **Managed portfolios** — distinguish MF vs PMS vs AIF by access, disclosure, and risk; respect eligibility.
7. **Portfolio construction** — diversification, asset allocation, rebalancing as *concepts*; weights come from deterministic backend.
8. **Ethics (Ch 19)** — fiduciary duty, conflict disclosure, no churning, no guaranteed returns, client interest first.
9. **Grievance (Ch 20)** — point to SEBI SCORES / exchange mechanisms when relevant; do not invent processes.
10. **Missing data stays unknown** — do not fill gaps with assumptions presented as facts.

## Output patterns

When explaining L1 topics in product/UI/copy:

```
What it is → Why it matters for planning → What the user should review → Disclaimer
```

Always include: source of any market/portfolio fact, as-of time, and “not a buy/sell instruction” where observations appear.

## Do NOT

- Issue personalized buy/sell/hold recommendations
- Guarantee returns or call anything risk-free
- Bypass risk profiling / suitability (covered more in L2)
- Treat this skill as a substitute for reading the live SEBI gazette / circulars

## Related

- L2 (insurance, tax, estate, behaviour, risk profiling): skill `nism-investment-adviser-l2`
- Retirement-focused NPS/PFRDA: skill `nism-retirement-adviser`
- Product explainability tone: `skills/financial-explainability.md`
