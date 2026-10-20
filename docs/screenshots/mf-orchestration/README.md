# Mutual funds and central orchestration: browser proof

These captures come from the running AI-cio application at `http://127.0.0.1:3100`, with its API on `8100`. All four accounts are explicitly synthetic. Their positions, quantities, finances, goals and confirmed test budgets are invented demonstrations. Scheme identities and available dated public NAV, AMC disclosures and published comparisons come from the actual provider adapters.

The browser ran normal decisions, verified the same stored decision on reload, resolved cited skill sections and checked a 390 px viewport. Positions and questionnaire records were unchanged. The import guard rejected an invalid local JSON file before an upload. No real account, trade, redemption or financial document import is involved.

## Observed checks

| Synthetic profile | Fund records | Verified identities | TRI history series | AMC-reported tables | Decision request to visible | Cached reload to visible | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| tom | 2 | 0 | 0 | 0 | 26.558 s | 7.592 s | Passed |
| maya | 1 | 0 | 0 | 0 | 24.976 s | 6.832 s | Passed |
| arjun | 1 | 0 | 0 | 0 | 22.251 s | 7.221 s | Passed |
| mf-evidence-demo | 3 | 3 | 0 | 2 | 25.676 s | 6.047 s | Passed |

Times are observations from these runs, including browser and local network work; they are not speed guarantees. Every account passed the mobile width, saved-budget restoration and unchanged-position/questionnaire checks. Five specialists have actual execution receipts. Each specialist has at least six scoped resources, and the shared portfolio pack has three. Availability of a resource is distinct from proof that its principle supported an accepted finding.

## Inspect the decision

| What to inspect | Capture |
|---|---|
| Central coordinator, five specialists, formulation stages and validation | [Central orchestration](mf-evidence-demo-central-orchestration.png) |
| Recorded overlapping task lifetimes | [Parallel timeline](mf-evidence-demo-parallel-timeline.png) |
| Mutual fund specialist's scoped sources | [Financial resource pack](mf-evidence-demo-financial-resource-pack.png) |
| Actual server-scrubbed model request and validation receipt | [LLM request and validation](mf-evidence-demo-llm-request-validation.png) |
| Exact cited project skill sections and supporting sources | [Applied skill](mf-evidence-demo-applied-skill.png) |
| A numerical overlap finding, its common-security receipt and resolved principles | [Overlap finding proof](mf-evidence-demo-overlap-finding-proof.png) |
| Actual fund identities, computed-metric gaps and source coverage | [Fund evidence](mf-evidence-demo-fund-evidence.png) |
| Dated, published plan comparison with explicit option limitations | [AMC-reported context](mf-evidence-demo-amc-reported-context.png) |
| Measured underlying-security overlap, with disclosed coverage | [Holdings overlap](mf-evidence-demo-holdings-overlap.png) |
| Fund-to-fund return correlation, separate from holdings overlap | [Return correlation](mf-evidence-demo-return-correlation.png) |
| Synthetic direct positions plus disclosed fund underlying positions | [Combined exposure](mf-evidence-demo-combined-exposure.png) |
| Invalid normalized JSON blocked before upload | [Evidence import guard](mf-evidence-demo-evidence-import-guard.png) |
| Coordinator on a narrow screen | [Mobile orchestration](mf-evidence-demo-mobile-orchestration.png) |
| Fund review on a narrow screen | [Mobile funds](mf-evidence-demo-mobile-funds.png) |

## Honest coverage and model outcomes

The MF evidence demo contains three real scheme identities and synthetic investment quantities. Two PPFAS schemes have automatically acquired official disclosures and AMC-reported trailing comparisons. An independently obtained benchmark TRI history is absent in this run, so matched-series benchmark charts and rolling benchmark statistics remain unavailable. Fund-to-fund correlation uses aligned fund NAV returns independently of TRI availability; supported pairs are shown with their observation counts and unsupported pairs remain unknown. AMC tables are separate reported context: their exact starting market dates and Growth/IDCW basis are not inferred. Other AMCs require a supported adapter or an applicable user-scoped official-data import; the interface does not invent their holdings.

Tom, Maya and Arjun retain their original illustrative holdings, including unresolved mutual fund identifiers. Their missing-evidence findings are appropriate outcomes, not fabricated performance judgments. Fund badges distinguish which holding needs attention without manufacturing different opinions about the same missing input.

The model's observed explanatory outcomes were:

- **tom**: `rejected`; 1 recorded model call(s).
- **maya**: `validated_explanation`; 1 recorded model call(s).
- **arjun**: `validated_explanation`; 1 recorded model call(s).
- **mf-evidence-demo**: `validated_explanation`; 1 recorded model call(s).

A rejected or unavailable explanation leaves the deterministic, skill-grounded findings in place. No run was repeated to force an accepted answer. JSON parsing, explanatory-content checks, financial arithmetic and source-integrity checks remain distinct in the recorded trace; a passed check is not a guarantee of a financial outcome.

## Existing personas

| Profile | Coordinator | Fund review | Mobile |
|---|---|---|---|
| Tom | [Trace](tom-central-orchestration.png) | [Evidence gaps](tom-fund-evidence.png) | [Fund view](tom-mobile-funds.png) |
| Maya | [Trace](maya-central-orchestration.png) | [Evidence gaps](maya-fund-evidence.png) | [Fund view](maya-mobile-funds.png) |
| Arjun | [Trace](arjun-central-orchestration.png) | [Evidence gaps](arjun-fund-evidence.png) | [Fund view](arjun-mobile-funds.png) |

Images show actual completed analyses and their server-validated reloads. Cache-only MF demo recaptures reuse the same stored decision; expired original-persona analyses were refreshed rather than labelled current. A temporary screenshot-only stylesheet removes the sticky header while taking each component image and restores it immediately; product styling and financial text are unchanged.

Machine-readable checks, timestamps, task durations, budget constraints, source IDs and recapture receipts: [checks.json](checks.json).
