# Aryaman — AI-CIO Decision Pipeline (Demo Spec)

**Account:** Aryaman (`user_id: 1`, `aryamankochhar456@gmail.com`)  
**Objective shown:** `review_equity_portfolio`  
**Purpose:** Show exactly what goes **into** the system and what comes **out** — without exposing private LLM chain-of-thought.

Companion machine dumps (full JSON):

- `docs/aryaman_twin_summary.json`
- `docs/aryaman_equity_agent_input.json`
- `docs/aryaman_rule_insights.json`
- `docs/aryaman_tax_output.json`
- `docs/aryaman_fd_output.json`
- `docs/aryaman_trajectory_output.json`
- `docs/aryaman_decision_outputs.json`

Regenerate with:

```bash
python scripts/dump_aryaman_pipeline.py
```

---

## End-to-end flow

```text
HTTP POST /users/1/decisions
  { objective, constraints, force_refresh? }
        │
        ▼
┌───────────────────┐
│ Digital Twin      │  ← psychometrics, finances, goals, CAS holdings, FDs
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Deterministic     │  ← concentration, style/sector, portfolio flags
│ preanalysis       │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Equity agent      │  ← LLM explains/synthesizes structured payload only
│ (optional)        │     (math stays outside the model)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Tax / FD /        │  ← independent specialist engines
│ Trajectory agents │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Conflict detect + │  ← Decision Trace, Agent Perspectives,
│ CIO synthesis     │     Behaviour, Data quality
└─────────┬─────────┘
          ▼
DecisionResult JSON  →  Decisions UI
(+ cached if Twin fingerprint unchanged)
```

---

## 1. API request (what the UI sends)

### Format

```json
{
  "objective": "review_equity_portfolio",
  "available_capital": null,
  "constraints": {
    "goal_ids": [2, 3, 4, 5, 6],
    "min_liquid_reserve": null
  },
  "requested_action": null,
  "force_refresh": false
}
```

| Field | Meaning |
|--------|---------|
| `objective` | Which decision mode to run |
| `constraints.goal_ids` | Goals included in trajectory / likelihood |
| `force_refresh` | `false` → serve cache if Twin unchanged; `true` → recompute |

### What Aryaman actually sends (typical)

```json
{
  "objective": "review_equity_portfolio",
  "constraints": {
    "goal_ids": [2, 3, 4, 5, 6]
  },
  "force_refresh": false
}
```

---

## 2. Digital Twin input (assembled before any agent)

### Format (shape)

```json
{
  "user": { "id": number, "name": string },
  "completeness": { "psychometric": bool, "income": bool, "portfolio": bool, "..." : bool },
  "behaviour": { "status": "known|unknown", "scores": {}, "observations": [] },
  "financial_position": {
    "income": { "value": string, "known": bool },
    "expenses": { "value": string, "known": bool },
    "liquid": { "value": string, "known": bool },
    "fixed_deposits": { "items": [], "total_principal": string },
    "liabilities": { "items": [], "total": string }
  },
  "goals": { "items": [ { "id", "name", "goal_type", "target_amount", "current_funding", "horizon_years" } ] },
  "portfolio": {
    "total_value": { "value": string, "source": string },
    "holdings": [ { "isin", "scheme_name", "asset_class", "valuation", "closing_units", "nav" } ],
    "snapshots": [ { "month_year", "valuation", "change_pct" } ]
  }
}
```

### What is actually on Aryaman’s Twin

| Area | Value |
|------|--------|
| Completeness | All core flags **true** (psychometric, income, expenses, liquid, goals, portfolio, horizon) |
| Income / expenses / liquid | ₹1,00,000 / ₹70,000 / ₹4,20,000 |
| Portfolio value (CAS) | ₹12,57,065.12 · **26** holdings · **14** direct equity |
| FDs | HDFC ₹2,50,000 @ 7.10% (matures 2027-01-15); SBI ₹1,50,000 @ 6.80% (matures 2026-06-01) |
| Liability total (trajectory) | ₹2,85,000 |
| Psychometric risk | **41.7** (moderate / cautious) |
| Other scores | Loss aversion 50 · Anchoring 66.7 · Recency 37.5 · Herding 83.3 · Overconfidence 37.5 · Decision stability 75 · Profile confidence 38.9 |

**Goals**

| Goal | Target | Funded | Horizon |
|------|--------|--------|---------|
| Emergency fund top-up | ₹6,00,000 | ₹1,80,000 | ~1y |
| Home down payment | ₹80,00,000 | ₹9,50,000 | ~6y |
| Retirement corpus | ₹3,50,00,000 | ₹22,00,000 | ~22y |
| Child education | ₹25,00,000 | ₹3,20,000 | ~9y |
| Europe trip | ₹4,50,000 | ₹75,000 | ~3y |

**Top holdings (by valuation)**

| Name | Type | ~Value |
|------|------|--------|
| Parag Parikh ELSS Tax Saver (Direct) | MF | ₹3,17,117 |
| HDFC Bank | Equity | ₹1,45,971 |
| Kotak Midcap Direct Growth | MF | ₹1,33,540 |
| SBI Small Cap Direct Growth | MF | ₹1,21,227 |
| PGIM India Midcap Direct | MF | ₹1,20,837 |
| Nippon India Small Cap Direct | MF | ₹88,759 |
| BSE Limited | Equity | ₹66,338 |

**Month-end snapshots (sample)**

| Month | Valuation | MoM % |
|-------|-----------|-------|
| Jun 2025 | ₹11,94,890 | — |
| Jul 2025 | ₹11,85,531 | −0.78% |
| Aug 2025 | ₹12,11,327 | +2.18% |
| Sep 2025 | ₹12,32,423 | +1.74% |
| Oct 2025 | ₹12,66,234 | +2.74% |
| Nov 2025 | ₹12,63,279 | −0.23% |

---

## 3. Deterministic preanalysis (input to equity agent)

Computed in code — **not** invented by the LLM.

### Format

```json
{
  "portfolio_snapshot": { "number_of_holdings": number, "total_valuation": string },
  "concentration": {
    "largest_holding_percent": string,
    "top_3_holdings_percent": string,
    "largest_amc_percent": string,
    "largest_sector_percent": string
  },
  "portfolio_flags": { "high_single_holding_concentration": bool, "...": bool },
  "financial_health": { "liquid_assets_to_monthly_expenses": string },
  "holding_metrics": [ { "instrument_type", "weight_percent", "..." } ]
}
```

### What Aryaman actually gets

| Metric | Value |
|--------|--------|
| Largest holding | **25.23%** |
| Top 3 | **47.46%** |
| Top 5 | **66.72%** |
| Top 10 | **90.37%** |
| Small-cap style tilt | **~31.31%** |
| Financials / Banks (classified equity) | **~63.20%** |
| Liquidity cover | **~6 months** of expenses |

---

## 4. Equity agent — LLM input & output

### Input format (payload sent to the model)

```json
{
  "user": {},
  "behaviour": {},
  "goals": {},
  "financial_position": {},
  "completeness": {},
  "equity_sleeve": {
    "direct_equity_holdings": [],
    "equity_oriented_funds": [],
    "counts": { "direct_equity": n, "equity_oriented_funds": n, "all_holdings": n }
  },
  "preanalysis": { "portfolio_snapshot", "concentration", "portfolio_flags", "holding_metrics", "..." },
  "market_data": { "included": false, "note": "Live market prices intentionally omitted..." }
}
```

Plus domain skill excerpts (NISM / equity review guidance) in the system prompt.

**Rules enforced in the prompt:** no invented prices/holdings; no ticker buy/sell orders; return structured JSON only.

### Expected LLM output format

```json
{
  "observations": ["...", "..."],
  "risks": ["...", "..."],
  "tradeoffs": ["...", "..."],
  "decision": "One clear decision summary for human review.",
  "recommended_actions": ["...", "..."],
  "assumptions": ["..."],
  "missing_information": ["..."],
  "confidence": "low|medium|high",
  "key_factors": ["...", "..."],
  "knowledge_used": [{ "source": "skill", "section": "...", "content": "..." }]
}
```

### What the rule-based layer already produces for Aryaman
(Always available; LLM synthesizes/explains when configured — does not redo the maths.)

**Decision summary**

> Equity sleeve decision: address concentration and sector/style imbalance before seeking new high-conviction names.

**Observations (sample)**

- Largest holding ~25.23% of invested value  
- Top 3 ~47.46%  
- Style tilt ~31.31% small cap  
- Sector tilt Financials/Banks ~63.20% of classified direct equity  
- Psychometric risk 41.7 (willingness ≠ capacity)  
- Near-term emergency + home goals should gate aggressive equity adds  

**Recommended actions (sample)**

- Review trimming / pausing SIPs into the largest holding (~25.23%); redirect new equity toward underrepresented styles/sectors  
- Spread new investments so top-3 share can drift lower  
- Review adding large-cap / broad index vs ~31% small-cap sleeve  
- Because Financials/Banks is ~63%, diversify **new** buys toward lighter sectors  
- Near-term emergency goal → keep larger cash/debt buffer  

**Trade-offs**

- Cut small-cap → lower vol, may cut growth upside  
- Cut Financials/Banks → less sector risk, may lag if sector leads  

---

## 5. Tax agent

### Input (implicit)

Holdings + transactions from CAS/broker data → deterministic lot engine (`fy2026-27.v1`).

### Output format

```json
{
  "available": true,
  "agent": "tax_agent",
  "rule_version": "fy2026-27.v1",
  "summary": {
    "stcg": string, "ltcg": string, "unrealized_gains": string, "unrealized_losses": string,
    "estimated_tax": string
  },
  "opportunities": [
    {
      "type": "tax_loss_harvesting",
      "security": string, "isin": string, "amount": string,
      "estimated_tax_impact": string, "confidence": number,
      "reason": string, "risks": [], "label": string
    }
  ],
  "comments": [],
  "data_quality": {},
  "disclaimer": "..."
}
```

### What Aryaman actually gets

| Field | Value |
|--------|--------|
| Realized STCG | ₹351.17 |
| Realized LTCG | ₹0 |
| Unrealized gains | ₹47,880 |
| Unrealized losses | ₹65,400 |
| Estimated CG tax | **₹70.23** |
| TLH opportunities | **4** (HDFC Bank ~₹40.9k loss, BSE ~₹18.6k, Jain Resource ~₹2.8k, Kotak Midcap lot ~₹1.9k) |

Educational estimates — **not tax advice**.

---

## 6. FD / cash agent

### Output format

```json
{
  "available": true,
  "summary": {
    "fd_count": number,
    "total_principal": string,
    "liquid_cash": string,
    "combined_cash_and_fd": string
  },
  "comments": [],
  "opportunities": []
}
```

### What Aryaman actually gets

| Field | Value |
|--------|--------|
| FD count / principal | 2 / ₹4,00,000 |
| Liquid cash | ₹4,20,000 |
| Cash + FD | **₹8,20,000** |

---

## 7. Trajectory / goals engine (deterministic maths)

### Output format

```json
{
  "available": true,
  "score": { "overall_score": number, "label": string, "component_scores": {}, "explanations": [] },
  "snapshot": { "net_worth", "monthly_surplus", "savings_rate_percent", "liquid_months_cover", "..." },
  "behavior": { "available": bool, "behavior_score": number, "comments": [], "components": {} },
  "projections": {
    "scenarios": { "conservative": "6%", "base": "10%", "optimistic": "14%" },
    "horizons": [5, 10, 15, 20, ...],
    "endpoints_by_horizon": {}
  },
  "goal_projections": [],
  "insights": [],
  "recommended_actions": [],
  "disclaimer": "Illustrative — not a prediction"
}
```

### What Aryaman actually gets

| Field | Value |
|--------|--------|
| Trajectory score | **70 / 100** — “Mixed trajectory” |
| Net worth (illustrative) | ₹17,92,065 |
| Monthly surplus | ₹30,000 (30% savings rate) |
| Liquid months | ~6.0 |
| Observed behaviour score | **44** |
| Txn history | 33 dated txns · 24 buy-like · 7 sell-like · ~81.5 events/year proxy |

**Score supports:** savings rate, goal progress, liquidity  
**Score reduced by:** risk alignment, investment consistency  

**Goal funding (base ~10% p.a. illustrative)**

- Emergency → `possible`  
- Home down payment → `at_risk` (suggest ~₹65,287/mo under base assumptions)  
- Retirement → `likely`  

---

## 8. Composed Decision Result (what the UI shows)

### Top-level output format

```json
{
  "decision_id": string,
  "user_id": 1,
  "objective": "review_equity_portfolio",
  "decision": string,
  "confidence": "medium",
  "rationale": [],
  "recommended_actions": [],
  "risks": [],
  "tradeoffs": [],
  "tax_intelligence": {},
  "fd_intelligence": {},
  "trajectory_intelligence": {},
  "decision_trace": {},
  "agent_perspectives": {},
  "temporal_changes": {},
  "behavioral_intelligence": {},
  "data_quality": {},
  "cache": { "hit": bool, "note": string }
}
```

### Agent perspectives (Aryaman)

| Agent | Finding | Recommendation | Stance conflict |
|--------|---------|----------------|-----------------|
| Portfolio / Equity | Address concentration & sector/style imbalance | Trim/pause SIPs into largest ~25.23% holding | Conflicts with Tax |
| Tax | TLH opportunity | Review tax lots before realizing | Conflicts with Portfolio |
| FD / cash | ₹4L across 2 FDs | Not evaluated | — |
| Goals / Trajectory | Mixed trajectory (70) | Check if ₹30k surplus matches SIPs | — |
| Sector rules | Depends on Dhan at run time | — | — |

**Key disagreement**

- Portfolio: **REDUCE / REVIEW** concentration  
- Tax: **HOLD / REVIEW TAX LOTS** (TLH / realization caution)  
- Conflict: risk reduction vs tax realization  

**CIO synthesis**

> Address concentration and sector/style imbalance before seeking new high-conviction names.  
> Agreement: **mixed**

### Decision Trace steps (observable — not private CoT)

1. **Inputs** — Portfolio ₹12.57L · Liquid ₹4.2L · Largest holding 25.23% · Est. CG tax ₹70  
2. **Observations** — concentration, small-cap tilt, Financials overweight, goal horizons  
3. **Calculations / rules** — key factors + tax/trajectory assumptions  
4. **Specialist findings** — cards above  
5. **Conflicts** — REDUCE vs tax caution + documented style/sector trade-offs  
6. **CIO synthesis** — mixed agreement conclusion  
7. **Final finding** — decision + recommended actions + confidence  

### Observed investment behaviour

| Declared | Observed | Divergence |
|----------|----------|------------|
| Moderate risk (~42/100) | Largest holding ~25%; elevated trading frequency | Stated moderate risk vs high single-holding concentration (causation **not** claimed) |

### What’s changed?

Derived only from Twin snapshots (Jun→Nov 2025 valuation path) — never fabricated history.

### Data quality

Surfaces Verified / Incomplete / Conflicting / Stale / Unknown from Twin completeness + tax cost-basis coverage.  
Example note: *Confidence: Medium — multiple incomplete inputs* (e.g. tax efficiency component / cost lots).

---

## 9. What the AI is (and is not) doing

| Does | Does not |
|------|----------|
| Read Twin + CAS holdings/transactions | Invent holdings, prices, or sectors |
| Run deterministic concentration / tax / projection maths | Ask the LLM to do portfolio maths |
| Let the equity LLM **explain & synthesize** structured JSON | Expose private chain-of-thought |
| Detect agent disagreement (e.g. trim vs tax caution) | Auto-execute trades |
| Cache results until Twin fingerprint changes | Silently overwrite conflicting data |

---

## 10. Caching (demo note)

After one successful run for Aryaman:

- Re-open **Decisions** or click Proceed with unchanged data → `cache.hit: true`  
- No new LLM / Dhan / full agent recompute  
- Click **Refresh analysis** (`force_refresh: true`) only when you want a fresh compute  

Fingerprint includes: holdings, transactions, goals, psychometrics, finances, FDs, objective, constraints.

---

*Generated from live DB user_id=1 via `scripts/dump_aryaman_pipeline.py`. Figures are analytical / educational — not SEBI-registered advice or tax advice.*
