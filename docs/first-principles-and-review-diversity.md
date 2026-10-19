# Cited derivations and distinct financial reviews

AI-cio now publishes one canonical review record for each actionable finding: recorded facts, reproducible arithmetic, an exact applied skill excerpt, a conditional next step, and missing information. The headline, ranked actions, specialist links and evidence use those same records. Tax and FD pages expose the same source checks.

Twenty registered principles resolve against actual headings and excerpts in `.cursor/skills/*/SKILL.md`. Unknown, removed or changed excerpts fail closed. Each citation includes a section, line reference and normalized-text SHA-256. The on-page verification button compares the published quote and hash with the current source endpoint. It verifies source integrity, not investment outcomes.

These are project-authored condensed guides. Their excerpts are not presented as quotations from complete books or as proof that a recommendation satisfies every regulatory requirement. Primary-source context remains separate from the applied project principle.

## Examples from the worked personas

| Persona | Leading review | Derivation and next question |
|---|---|---|
| Tom | Retirement assumptions | Four years to retirement; establish spending, pension, inflation and withdrawal assumptions before treating a nominal corpus as adequate. |
| Maya | Reserve earmarking | Recorded target ₹390,000 minus funded amount ₹250,000 leaves ₹140,000. Confirm which assets back the reserve before allocating the same cash elsewhere. |
| Arjun | Shared goal budget | ₹175,000 income minus ₹120,000 outgoings leaves ₹55,000 monthly surplus shared by three goals. Compare priorities, dates and contributions together. |

The reserve duration is this scenario's planning assumption, not a universal minimum. No-return goal comparisons are baselines, not forecasts or required contributions. Independent goal projections do not constitute joint allocation. Annual cashflows are normalized to months; unknown cadence cannot establish monthly capacity. EMI included in recorded expenses is not deducted twice.

Relevant skill text includes:

- [Goal planning](../.cursor/skills/nism-investment-adviser-l1/SKILL.md): “The same cash cannot independently fund every goal; overlapping funding is a limitation unless the engine implements joint allocation.”
- [Liquidity](../.cursor/skills/liquidity-and-deposit-safety/SKILL.md): “Coverage ratios require an identified denominator and cadence.”
- [Retirement](../.cursor/skills/nism-retirement-adviser/SKILL.md): “A nominal corpus is not purchasing power.”
- [Tax coverage](../.cursor/skills/tax-source-discipline/SKILL.md): “Missing dates or cost basis mean not evaluated for affected calculations, rather than zero tax.”
- [Costs](../.cursor/skills/common-sense-investing/SKILL.md): “Unknown costs stay unknown.”

## Repetition and ranking

There is at most one finding per causal theme, capped at eight, without a minimum that forces filler. Reviews can cover reserves, debt terms, shared goals, retirement income, deposit access and eligibility, tax coverage, costs, market evidence and exposure. Data determines which appear and lead. Concentration cannot fill multiple cards.

Specialists have distinct mandates and link to the canonical findings. They are not represented as independent votes or forced to disagree. Repeated findings, worries, opportunities and action panels are suppressed for the new review format. Counterfactuals link to relevant evidence without claiming that it proves a scenario outcome.

Review priority scores and normalized relative support express application triage. They are not probabilities of success or thresholds prescribed by a source. Missing fundamentals do not become a buy signal; missing tax records do not become zero liability; deposit eligibility is not an inferred insured balance.

## Verification

All four pre-commit gates passed: typecheck, lint, production build and backend tests. Backend: 243 passed, four skipped, one existing deprecation warning. Frontend tests: eight passed. Lint retained three existing warnings.

Browser checks ran one decision for each synthetic persona through the PowerShell-launched production application. All three had cited findings, matching published actions, one concentration card, zero duplicate advice panels, matching source verification, no page errors and no mobile horizontal overflow with the proof open. Tax and FD source checks also matched.

See the [23-image proof gallery](screenshots/skill-proofs/README.md) and [machine-readable validation](validation/skill-proofs.json). Profile finances are synthetic. Dhan daily history is real provider data, dated separately; these captures do not claim streaming prices or execution.
