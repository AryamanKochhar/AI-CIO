# AI-CIO product improvements

Implementation in this delivery builds on the cloned repository. It does not claim that the additions were part of the original academic implementation.

## Demo personas and reproducible psychometrics

The home page has three selectable synthetic profiles: Tom (56, dual income, no children, approaching retirement, IAS interpreted as Indian Administrative Service), Maya (28, early career, home deposit) and Arjun (42, single income, two children, education goal). The expanded home-page answer table shows every question and fixed answer for the selected profile. Confidence (75/100) and response time (5 seconds) are explicitly synthetic inputs.

`GET /demo/personas` returns the catalogue. `POST /demo/personas/{persona_id}/launch` creates a fresh isolated user and uses the existing canonical assessment services to submit and score all 18 responses. It then records synthetic finances, one goal and three illustrative category holdings, and advances the journey to analysis. No real identity, bank connection, NAV, return history or live stock holding is implied. Fixtures require instrument version 1.0; an incompatible instrument is rejected rather than silently generating new answers. Each new launch creates another demo user; production rate limits and demo retention policies remain future deployment work.

## A financial twin that grows visually

An accessible SVG companion appears on the home overview and twin page. It also appears throughout onboarding, reflecting saved Twin completeness. Psychometrics add glasses (mind), income adds a toolkit, liquid savings add a shield, goals add a compass, and portfolio information adds a growth chart. Each accessory has a corresponding text link to the relevant form. The interface distinguishes information availability from financial health: a shield means liquid savings were recorded, not that reserves are adequate. Unknown inputs remain unknown. The companion is rendered in ordinary UI code and needs no external asset-generation service.

## Ranked decision suggestions

The suggestion builder preserves rule-backed items before adding distinct LLM narrative. A deterministic policy ranks suggestions for review: risk = 90, diversification = 80, goals = 75, sector = 60, general = 40. Rule evidence receives a multiplier of 1; other narrative receives 0.75. Ties preserve input order. The normalized distribution is:

`relative_support_i = 100 × priority_score_i / sum(priority_score_j)`

Largest-remainder rounding makes the displayed percentages sum to exactly 100.00. The result includes rank, priority score, relative support, ranking basis and `calibrated_probability: false`. The UI shows a bar and action link for each suggestion plus an expandable methodology. For example, rule risk 90, AI risk 67.5 and rule sector 60 receive 41.38%, 31.03% and 27.59% of the review-priority distribution.

These percentages are a distribution over policy priorities within the displayed list. They are not the probability that an investment will profit, that a recommendation is correct, or that a goal will succeed. There is no outcome-labelled dataset, backtest or calibration study establishing such a claim. The policy weights are explicit implementation choices, not empirically estimated parameters. Goal percentage labels in the result and trajectory UI also identify the existing figures as heuristic coverage scores. Older cached results remain readable; refreshing analysis calculates the new ranking metadata.

## Clear actions across the journey

Twin, Decisions, Tax, FDs and News share the flow: check your twin, compare suggestions, check tax trade-offs, review liquidity. The Twin has a prominent decision CTA. Ranked suggestions link directly to supporting profile data or the appropriate goal/tax/FD page. Existing tax/FD specialist views, portfolio charts, decision traces, counterfactuals and news integration remain available. The decision result avoids duplicating suggestion prose in the separate opportunity list.

## Source-grounded knowledge

The repository already contained five financial frameworks: NISM adviser levels 1 and 2, NISM retirement, Psychology of Money, and CANSLIM. This delivery adds `common-sense-investing` and `investment-policy-and-risk`, with primary links and source limitations recorded inside their SKILL files. The equity agent loads both additions. The suggestion narrative loads the two new guides. These are source-attributed prompt frameworks, not a vector retrieval database or a claim of full-book ingestion. The Bogle guide uses the public Wiley publisher description. The policy/risk guide uses CFA Institute professional guidance and SEC investor education. Current Indian tax law continues to come from the configured rule pack, rather than these general sources. The existing corrupt Darwin PDF remains blocked in the books inventory.

Sources verified on 19 October 2026:

- [Wiley: The Little Book of Common Sense Investing](https://www.wiley.com/en-us/the-little-book-of-common-sense-investing-the-only-way-to-guarantee-your-fair-share-of-stock-market-returns-updated-and-revised-p-9781119404507)
- [CFA Institute: Standard III(C), Suitability](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-iii-c)
- [CFA Institute: Basics of Portfolio Planning and Construction](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/basics-of-portfolio-planning-and-construction)
- [SEC Investor.gov: Asset Allocation and Diversification](https://www.investor.gov/introduction-investing/getting-started/asset-allocation)

## Verification

`tests/test_suggestion_ranking.py` checks risk-first ordering, the evidence factor, exact normalization, stable ties, empty input, input immutability and the absence of calibrated-probability claims. `tests/test_demo_personas.py` checks fixed complete answer sets, isolated repeated launches, canonical assessment completion, synthetic holdings and HTTP route behaviour. The project verification gates are TypeScript typecheck, frontend lint, production build, financial-map unit tests and the full PostgreSQL-backed Python suite. Final measured results are recorded in the delivery validation notes.

Final verification passed: 151 backend tests passed, 4 skipped; all 3 financial-map tests passed; TypeScript checks passed; frontend lint passed with five existing warnings; the final production build generated 17 static pages. Real Edge/Playwright interactions launched Tom, assembled the complete twin, ran a fresh decision and followed links to Tax and FDs with no page errors. Six reviewed screenshots include a focused ranking view with the full methodology expanded. External LLM/news/market credentials were not used to claim provider validation.

## Practical limits

External news, market and LLM integrations still require their documented credentials. The demos can be created without those services; unavailable providers must keep their honest fallback states. The original account model uses browser session state and user-ID routes; these additions do not convert that model into production-grade authentication. No account credentials, infrastructure secrets, repository commits, remote pushes or public deployment are included in this change.
