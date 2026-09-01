# Decision orchestration

This folder coordinates investment decisions. It does not replace the Digital Twin,
psychometric tests, or portfolio services. It reads from them and builds a decision.

## Flow

1. Receive a decision request (user, goal, amount, constraints).
2. Load existing user data through adapters.
3. Build an investment context.
4. Run analysis (today: simple rule-based allocator).
5. Evaluate strategies against the user's situation.
6. Validate hard rules (amounts must add up, no negatives).
7. Return a structured result.

## Files

- `coordinator.py` — runs the pipeline
- `context_builder.py` — loads and checks user data
- `adapters.py` — connects to twin, market, and knowledge services
- `strategy_evaluation.py` — scores candidate strategies
- `analyzers/simple_allocator.py` — first analyzer implementation

Domain types live in `apps/api/domain/decision/`.

## Adding a new analyzer

Implement the `DecisionAnalyzer` interface from `domain/decision/ports.py`
and pass it into `run_decision(..., analyzer=YourAnalyzer())`.

## Adding a new decision type

1. Add the objective to `DecisionObjective` in `domain/decision/contracts.py`.
2. Map capabilities in `domain/decision/capabilities.py`.
3. Handle it in the analyzer.
