# Future Architecture — AI-CIO

> Status: **PLANNED / NOT IMPLEMENTED**. Nothing below is in the current codebase. This document describes the intended future architecture once the current Step 1–4 target is stable.

## Planned steps 5–14

1. **Financial Intelligence**
2. **Specialist AI Agents**
3. **Portfolio Conference**
4. **AI-CIO Decision Synthesis**
5. **Constraint Validation**
6. **Simulation & Risk Evaluation**
7. **Explainability**
8. **Financial Action Plan**
9. **Human Review**
10. **Feedback & Memory**

## Contracts for future agents (implemented in market intelligence tranche)

Future specialist agents should consume without rewriting:

- `MarketSnapshot`, `SectorAnalytics`, `PortfolioExposure`
- `OpportunityCandidate`, `TwinAnalysisContext`, `KnowledgeReference`
- `MarketOpportunityAnalysis`

Current tranche stops at observation + optional LiteLLM interpretation — not decision synthesis.

- Equity Agent
- Mutual Fund Agent
- ETF Agent
- Debt Agent
- Cash / Liquidity Agent
- Risk Agent
- Goal Planning Agent
- Behaviour Agent
- Tax Agent
- Macro Agent
- News Agent
- Crypto Agent
- Derivatives Agent

### Specialist agent lifecycle

Each specialist agent will follow the same loop:

```text
OBSERVE → REMEMBER → ANALYSE → PROPOSE → CRITIQUE → PARTICIPATE IN CONFERENCE → REFLECT
```

- **OBSERVE**: read the user's Digital Financial Twin, portfolio, goals, constraints, and any market data.
- **REMEMBER**: consult its own memory and past context.
- **ANALYSE**: run deterministic analysis and reasoning within its domain.
- **PROPOSE**: emit a structured proposal with rationale and evidence.
- **CRITIQUE**: examine other proposals and identify conflicts or risks.
- **PARTICIPATE IN CONFERENCE**: debate in a multi-agent portfolio conference.
- **REFLECT**: record lessons and update its memory after human review.

## Portfolio conference flow

```text
Specialist opinions → Evidence → Conflicts → Debate → Trade-offs → Consensus / Ranked alternatives → AI-CIO
```

1. Each agent submits an opinion with supporting evidence.
2. The conference layer detects conflicts and trade-offs.
3. Agents debate and critique one another.
4. The output is either a consensus recommendation or a ranked list of alternatives, plus explicit trade-offs.
5. That output is passed to the AI-CIO synthesis step.

## AI-CIO decision synthesis

The AI-CIO synthesis will consume:

- Digital Financial Twin
- Goals
- Capacity and willingness to take risk
- Liquidity position
- Portfolio holdings
- Specialist agent opinions
- Conference outcome
- Constraints
- Scenarios and uncertainty

It will produce:

- Recommended actions
- Rationale
- Risks
- Alternatives
- Assumptions
- Confidence
- Agent contributions
- Goal impact

The AI-CIO will **not** execute trades autonomously. It will always stop at human review.

## Market data boundary

Future market data will flow through a dedicated boundary:

```text
Market Data → Market Data Service → Portfolio / Intelligence
```

No random external API calls from agents, services, or UI. All market data access will be centralized, rate-limited, and documented.

## Knowledge base

The knowledge base (currently `knowledge/*.md`) will stay separate from executable logic. There is no vector database in the current or planned near-term architecture.
