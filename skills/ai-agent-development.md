# Skill: AI Agent Development

## Purpose

Govern the future addition of AI reasoning agents to AI-CIO. Agents must consume the assembled Digital Financial Twin, follow a structured lifecycle, remain human-in-the-loop, and never reconstruct finances independently or place autonomous trades.

## When to use

- Designing or implementing future AI-CIO reasoning/analysis features.
- Adding agentic behaviour around the "Analysis" or "Decide" journey steps.
- Integrating LLMs, planning systems, or recommendation engines.
- Defining memory, observation, critique, or conference mechanisms for agents.

## Architectural constraints

- **Agents are NOT implemented yet.** This playbook governs their future addition.
- The canonical source of financial truth for agents is the **Digital Financial Twin** (`GET /users/{user_id}/twin`).
- Agents must **not** reconstruct a user's finances independently from raw documents or scattered tables.
- Agents operate in a **human-in-the-loop** mode: propose, do not execute.
- Agents must **not** place autonomous trades, transfers, or orders.
- Agents follow the lifecycle: **OBSERVE → REMEMBER → ANALYSE → PROPOSE → CRITIQUE → CONFERENCE → REFLECT**.

## Files to inspect first

1. `ai_cio/services/twin.py` — Digital Financial Twin assembly.
2. `ai_cio/api/routes.py` — `GET /users/{user_id}/twin` route.
3. `ai_cio/services/review.py` — human review assembly.
4. `ai_cio/services/journey.py` — decision capture and lifecycle.
5. `docs/current-architecture.md` — Twin status and analysis/decide placeholders.
6. `docs/privacy-and-limitations.md` — privacy constraints.

## Implementation rules

1. **Consume the Twin**: agents read from `GET /users/{user_id}/twin`. The Twin already carries provenance and `known` flags; agents must respect them.
2. **No independent reconstruction**: agents must not re-parse CAS PDFs, re-score psychometrics, or rebuild net worth from raw tables. If the Twin is incomplete, the agent reports gaps, not guesses.
3. **Lifecycle adherence**:
   - **OBSERVE**: read the Twin and note completeness.
   - **REMEMBER**: recall prior decisions, constraints, and user preferences from `UserJourney` and future memory stores.
   - **ANALYSE**: evaluate the financial situation against goals and constraints using deterministic domain helpers.
   - **PROPOSE**: generate one or more candidate recommendations with reasoning.
   - **CRITIQUE**: evaluate each candidate for risks, conflicts, and uncertainty.
   - **CONFERENCE**: present candidates and critique to the human for review.
   - **REFLECT**: after a decision is recorded, update memory and explain the outcome.
4. **Human-in-the-loop**: every proposal stops at the human. Execution of any financial action (if ever added) requires explicit human confirmation outside the agent loop.
5. **No autonomous trades**: the system does not place orders, initiate transfers, or modify holdings without human action.
6. **Unknown stays unknown**: when the Twin marks something unknown, the agent must not fabricate it.
7. **Decision capture**: final acceptance/modification/rejection is recorded via `journey_svc.record_decision()`.
8. **Auditability**: agent reasoning steps should be logged in a structured, reviewable form, not hidden inside prompt internals.

## Testing requirements

- Unit tests for each lifecycle stage using a mock Twin payload.
- Tests that verify the agent does not fabricate unknown Twin fields.
- Tests that verify no trade/transfer execution occurs without human confirmation.
- Tests that verify agent outputs are deterministic given the same Twin.
- Run `pytest -q` before finishing.

## Do NOT

- Implement autonomous trading or transaction execution.
- Reconstruct the Twin from raw tables or documents inside the agent.
- Skip the human review step.
- Store sensitive user data in external LLM logs or prompt caches without explicit handling.
- Add agent code that bypasses the Twin API contract.
- Pretend agents are already implemented; this is future work.

## Definition of done

- [ ] Agent reads from `GET /users/{user_id}/twin` only.
- [ ] Lifecycle stages are explicit and testable.
- [ ] Human-in-the-loop checkpoint exists before any proposed action.
- [ ] No autonomous trade or transfer execution.
- [ ] Unknown Twin fields are preserved as unknown.
- [ ] Tests cover lifecycle stages and no-fabrication/no-autonomy invariants.
- [ ] `pytest -q` passes.
