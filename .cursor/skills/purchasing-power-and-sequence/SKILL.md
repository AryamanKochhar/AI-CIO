---
name: purchasing-power-and-sequence
description: Explain purchasing power, longevity and withdrawal order with explicit assumptions and original derivations.
---
# Purchasing power and withdrawal order

Sources: cfa_wealth_risks and sebi_investment_constraints in knowledge/finance_sources.json. Original applied notes based on public summaries; no claim to the full CFA reading.

## Measure consumption rather than account digits
Nominal wealth counts currency units; purchasing power counts what those units buy. For a single matched period, real return = (1 + nominal net return) / (1 + inflation) - 1. Subtracting inflation is only an approximation. Use the same currency, horizon and compounding basis. A positive nominal return can still lose purchasing power. Missing inflation leaves real outcomes unevaluated.

## Separate saving from spending down
Without cashflows, multiplication of the same return factors gives the same endpoint regardless of order. With end-period withdrawals, W[t+1] = W[t] * (1 + r[t]) - withdrawal[t]. Return order then affects the capital left to recover. Matching average returns does not match withdrawal outcomes. State withdrawal timing and inflation adjustment. Do not infer a safe withdrawal rate or probability from a constant-return path.

## Make uncertainty actionable
Ask for retirement spending in today's or future rupees, date, pension, earmarked assets and essential commitments. Review contribution, timing or spending alternatives. Do not manufacture pension from occupation, longevity from age, or healthcare costs from a generic rule. This skill supplies an explanation; user-specific values require recorded facts.
