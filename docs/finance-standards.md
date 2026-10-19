# Finance review standards and source governance

AI-CIO uses finance knowledge to improve the relevance of its explanations. The Twin and deterministic services remain the authority for user facts and numbers. These standards do not certify the product as a registered adviser, prove suitability, or validate the existing tax engine against every applicable provision.

## What a useful finding contains

1. **Observed fact:** identify the input or engine result, its scope, source/date and denominator where available.
2. **Significance:** connect that fact to a recorded goal, liquidity need, obligation or policy constraint. Do not infer the constraint from age, occupation or a persona description.
3. **Conditional options:** compare supported review paths, including maintaining the current position where relevant. Do not create a transaction instruction.
4. **Trade-offs:** explain relevant risk, liquidity, costs, taxes and reversibility. An unknown amount stays unknown.
5. **Specific next action:** say which fact, calculation or page to inspect and what that review would resolve.
6. **Sources and gaps:** distinguish educational context from evidence about the user. Include missing inputs even if a model omits them.

The existing result fields implement this structure: observations describe facts; risks explain significance; tradeoffs compare conditional options; recommended_actions give review steps; evidence and missing_information expose the basis and limits. Empty arrays are valid when there is no supporting evidence. Model fluency and a minimum item count are not quality measures.

## Financial reasoning boundaries

- **Risk:** declared willingness, financial capacity and required goal return are different questions. A questionnaire score does not establish loss capacity. Income stability, essential spending, liabilities, dependants and insurance can materially affect capacity.
- **Liquidity:** distinguish accessible cash, earmarked funds, assets valued on a statement and deposits with withdrawal conditions. Reserve months are explicit planning assumptions, not a universal legal requirement.
- **Goals:** inspect priority, timing, flexibility and earmarked assets. Do not independently allocate the same savings to several goals. Existing independent goal paths do not establish a jointly funded plan.
- **Retirement:** separate accumulation from withdrawals. Name nominal/real, inflation, contribution and return assumptions. A constant-return path does not assess sequence risk, longevity sufficiency or a safe withdrawal rate.
- **Diversification and costs:** compare exposure, not just fund count. Identify unclassified look-through. Explain the difference between contribution-led and sale-led rebalancing, with known cost/tax/access constraints. Do not invent target bands or expected savings.
- **Deposits:** insured-bank identity and aggregated ownership/capacity facts are needed before discussing an account's insurance coverage. The DICGC source does not imply that every deposit or debt investment is insured or immediately accessible.
- **Tax:** require the transaction/income period, asset type, acquisition/disposal records, cost basis and applicable engine rule version. TDS and final liability are different. No model-memory rates, invented exemptions or promised harvesting savings.

The official transition FAQ distinguishes periods beginning before 1 April 2026 from periods under the Income-tax Act, 2025. This context does not update engine rates, validate historical calculations or permit applying today's rules to every historical transaction. [Income Tax Department transition FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act-faq).

## Runtime integration

`knowledge/finance_sources.json` is the maintained source manifest. It records stable IDs, publisher, direct URL, source type, verification date, scope, edition/effective context and review interval. It maps sources to the nine finance skills and local knowledge documents. Review intervals are application maintenance policy, not expiry periods stated by the publishers. A source outside its interval is labelled `review_due`; that flag does not claim the source changed.

`services/finance_standards.py` builds an explicit coverage and source context for the equity analyzer. It reports missing data without calculating new risk, tax, deposit-cover or return figures. Zero amounts remain known; non-finite values and booleans do not become financial facts. The context separates declared willingness from incomplete capacity assessment.

`agents/skills_loader.py` retains the original five book-related frameworks and the two previously added frameworks, adds liquidity/deposit and tax-source skills, strips discovery frontmatter from prompt excerpts, and excludes tooling/path-traversal names. Source metadata travels outside truncated skill excerpts. Evidence rows say that a framework was supplied; they do not claim that the model demonstrably applied it.

`agents/equity_agent.py` passes this context into the model, accepts empty supported arrays, appends required missing information and limits confidence when key inputs are absent. Without holdings it skips model and market calls. Model-cited knowledge must resolve to a supplied source ID; URLs, titles and source scope come from maintained metadata rather than model text. An identified source is still not independent proof of the model's interpretation.

The keyword retriever includes goal, retirement, liquidity and tax contexts with source IDs and the manifest version. Its adapters can preserve existing contracts. Tax and FD engines remain deterministic; they do not gain an LLM or a new legal-rate calculation from this change.

## Primary sources checked 20 October 2026

| Source | Use in AI-CIO | Boundary |
|---|---|---|
| [CFA Institute: Suitability](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-iii-c) | Whole-portfolio context, constraints and policy review | Professional standard; not Indian tax law |
| [CFA Institute: Portfolio planning](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/basics-of-portfolio-planning-and-construction) | Risk capacity versus willingness, liquidity and horizon | Educational principles; no personalized allocation default |
| [SEBI: Investment advisers](https://investor.sebi.gov.in/investment_advisor.html) | Suitability, transparent fees and avoiding guarantees | Investor education does not establish product registration |
| [SEBI: Direct and regular plans](https://investor.sebi.gov.in/regular_and_direct_mutual_funds.html) | Cost and plan-mechanics comparisons | Actual product costs must be supplied and dated |
| [NISM: Investment Adviser Level 1 objectives](https://www.nism.ac.in/wp-content/uploads/2021/08/Investment-Adviser-Level-1-Details.pdf) | Financial planning, goal priority and cash-flow scope | Public 2021 objectives; not asserted to be the latest workbook or legal rates |
| [NISM: Investment Adviser Level 2 curriculum](https://www.nism.ac.in/revamp-nism/curriculum-investment-adviser-level-2/) | Integrated planning and cross-domain review | Curriculum does not validate individual decisions |
| [NISM: Retirement Adviser objectives](https://www.nism.ac.in/test-objectives-retirement-adviser) | Retirement needs, inflation and life-event review | No guaranteed corpus or withdrawal percentage |
| [DICGC: Deposit-insurance guide](https://www.dicgc.org.in/guide-to-deposit-insurance) | Insured-bank deposit aggregation and coverage conditions | Account-level coverage is unevaluated without ownership and bank totals |
| [Income Tax Department: New Act FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act-faq) | Date/period applicability during the 2026 transition | Context source, not a capital-gains rate table |

Books supply attributed educational lenses. They do not outrank official legal authority or substantiate live market facts. No full book text, paid workbook or external PDF is newly copied into the repository. The growth-stock framework has no implied regulator or CFA endorsement.

## Validation and remaining limits

`tests/test_finance_standards.py` checks source resolution, review-date flags, corrupt-manifest fallback, tool-skill exclusion, zero-versus-missing values, demographic non-inference, metadata-backed citations, retrieval provenance and empty/partial equity responses without live calls. `tests/test_equity_agent.py` covers the existing extraction and equity payload path.

These checks verify application boundaries; they do not prove every model sentence is factually grounded. Live-provider evaluation, professional review of tax coverage, empirical suitability evaluation and broader user testing remain separate work. Update a source's verification date only after reviewing the linked authority; a successful web request alone is not substantive revalidation.
