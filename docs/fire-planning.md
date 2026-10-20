# Financial independence goal and decision

Open **http://localhost:3100/fire**. The API uses **http://localhost:8100**. The native launcher rejects reserved ports, validates the browser API URL and refuses to take an occupied port. Existing services are managed only through this checkout's PID/start-time records. Docker retains its container ports with separate loopback host mappings.

## User flow

Enter current age, target age (65 initially), retirement spending in today's rupees, pension expected at the target age in today's rupees, assets assigned only to this goal, and the total monthly amount the person agrees to invest. Explicit zero pension differs from missing pension. Record additional other-goal and reserve commitments only when they are not already included in expenses. Recorded expenses must include EMI.

Calculate a preview, inspect the funding gap, questionnaire effects, allocations and sources, then save the goal. Editing an existing goal updates it rather than creating duplicates. Input changes invalidate the displayed preview and disable saved-decision navigation until recalculated and saved. The decision page selects exactly one saved FIRE goal and uses its stored inputs.

```mermaid
flowchart LR
  A[Spending and target age] --> B[Inflation and retirement corpus]
  B --> C[Budget consent and cashflow capacity]
  C --> D[Psychometric and capacity limits]
  D --> E[Monthly allocation alternatives]
  E --> F[Dated bank FD terms]
  F --> G[Save goal and review decision]
```

## Calculation basis

Annual first-year retirement spending is `12 × current monthly spending × (1 + inflation)^years`. Pension entered in today's purchasing power is inflated to the same target date. The indexation choice governs pension increases after retirement, not the pre-retirement price basis.

The planner compares net annual spending divided by the selected withdrawal-rate assumption with a finite-retirement-horizon spending check at zero real return. For an unindexed pension, the second check includes its loss of purchasing power. The larger of the two is the planning corpus. This is an explicit application comparison, not an Indian safe-withdrawal-rate finding, a sequence simulation or a probability of success. The lifespan input changes the finite-horizon check.

The entered annual accumulation return is converted to an equivalent monthly rate. Contributions arrive at each month-end. The required contribution follows the annuity identity after subtracting growth of the explicitly earmarked opening balance. Twin assets are not added again. All allocation alternatives use the same entered return scenario; their investment returns are not separately forecast. Sensitivity shows lower, entered and higher return assumptions.

The monthly contribution is bounded by both total investment willingness and income minus expenses, with additional reserve/other-goal commitments deducted once from each applicable limit. For example, a total agreed budget of INR15000 and other-goal commitments of INR10000 leave at most INR5000 for FIRE. The planner reports a gap instead of raising risk or returns to make the goal appear funded.

## Actual psychometric effects

The lower of risk willingness and adaptive loss-sensitivity scores sets an illustrative equity preference: below20 →0%;20–39 →20%;40–69 →50%;70–100 →70%. Low decision stability adds a preference limit. These bands are transparent application policy, not a validated questionnaire-to-allocation standard. Horizon and recorded liquidity apply independent caps.

The result displays the raw scores, source, polarity, preference target, capacity cap, ranking distance and resulting rupee amounts. Other questionnaire dimensions add specific implementation checks for anchoring, recent-performance bias, herding and overconfidence. A funding gap cannot raise the permitted risk setting. Missing required scores leave allocation selection unconfirmed.

## FD comparison and evidence

The FD slice is a monthly set-aside. The dated SBI, HDFC and ICICI tenor cards are alternatives for a later eligible lump-sum booking, not nine additive instructions or recurring-deposit contracts. General gross card rates, conditional senior rates, minimum amount, access terms, eligibility, effective date and verification date remain visible. Stale or future-dated evidence cannot supply a current comparison rate or booking allocation. Future monthly booking and renewal rates remain unknown.

DICGC eligibility and aggregation concern the depositor's same-right/same-capacity deposits at one bank, including interest. The planner does not infer insured balances from partial account records or claim a universal best FD.

Seven exact project-skill excerpts resolve to real sections, line references, hashes and scoped primary-source metadata. The verification button compares displayed quotes with the current API source. It verifies citation integrity, not an investment outcome. See [primary-source research](fire-research.md).

## Integration and validation

- `POST /users/{id}/fire/preview` computes a plan without saving a FIRE goal.
- `POST /users/{id}/goals` and `PUT /users/{id}/goals/{goal_id}` persist validated FIRE assumptions.
- The `plan_fire` decision uses a saved, owner-scoped goal. Ambiguous or foreign goal selection fails.
- Existing decision fingerprints include goal JSON and behavioural profiles, so changed assumptions or scores invalidate cached plans.
- Migrations `0008_fire_goal_inputs` and `0009_fire_goal_type` add nullable `goals.planning_inputs` and extend the existing goal-type constraint. Existing goal rows are preserved; normal goals remain supported. A regression test exercises the legacy constraint upgrade rather than relying only on metadata-created tables.
- The FIRE decision path runs deterministic planning without a generic equity model or live market fetch.

Validation includes independent arithmetic checks, unknown and invalid inputs, total-budget earmarking, score polarity and allocation changes, stale FD handling, ownership, atomic edits and cache reuse/invalidation. The [browser proof gallery](screenshots/fire/README.md) records synthetic persona preview/save/decision flows on desktop and mobile. No orders are submitted.
