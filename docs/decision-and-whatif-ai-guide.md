# Decisions & What-if — AI data guide

How the **Decisions** run and **What-if (counterfactuals)** work, what structured data the LLM receives, and what JSON it must return.

**Design rule (hybrid):**

| Layer | Responsibility |
|-------|----------------|
| **Rules / Twin / engines** | Holdings, weights, tax maths, FD rates, trajectory projections, scenario numbers |
| **LLM** | Observation, narrative, ranking, “what to review” — **never invent** ₹ amounts, %, holdings, or trade orders |

Code entry: `apps/api/ai_cio/services/orchestration/coordinator.py` → `run_decision()`.

---

## 1. End-to-end Decision flow

```text
POST /users/{id}/decisions
  { "objective": "review_equity_portfolio" | "explore_counterfactuals" | ... }

        ▼
  Assemble Digital Twin (+ preanalysis)
        ▼
  Pick primary analyzer
    · Equity LLM  if equity/what-if + LLM configured
    · else SimpleAllocator (rules only)
        ▼
  Tax agent → FD agent → Trajectory (deterministic)
        ▼
  Decision Trace + Agent Perspectives
        ▼
  Counterfactuals (rules) → optional AI narrative
        ▼
  DecisionResult JSON → Decisions UI
```

Objectives that prefer the Equity LLM as primary analyzer:

- `review_equity_portfolio`
- `explore_counterfactuals`

---

## 2. Use A — Equity Decision Agent (LLM)

**File:** `apps/api/ai_cio/services/agents/equity_agent.py`  
**Class:** `EquityAgentAnalyzer`  
**When:** Equity / What-if objective + `EQUITY_AGENT_ENABLED` + LLM API key configured.

### 2.1 Messages sent to the LLM

1. **System:** role + domain skills (NISM L1, Psychology of Money, CANSLIM excerpts) + required output schema  
2. **User:** objective + `TWIN_EQUITY_PAYLOAD` JSON + knowledge snippets  

Live market prices are **intentionally omitted**.

### 2.2 Input JSON shape (`TWIN_EQUITY_PAYLOAD`)

Illustrative example (fields are real; values are samples):

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com"
  },
  "behaviour": {
    "status": "known",
    "source": "psychometric_assessment",
    "scores": {
      "risk_score": 55,
      "loss_aversion_score": 62,
      "risk_capacity_score": 48
    },
    "observations": ["Prefers gradual drawdowns over sharp losses."]
  },
  "goals": {
    "items": [
      {
        "name": "Retirement",
        "target_amount": "15000000",
        "target_date": "2045-01-01"
      }
    ]
  },
  "financial_position": {
    "liquid": { "value": "250000", "status": "known" },
    "monthly_income": { "value": "120000", "status": "known" },
    "monthly_expenses": { "value": "70000", "status": "known" }
  },
  "completeness": {
    "psychometrics": true,
    "finances": true,
    "goals": true,
    "portfolio": true
  },
  "equity_sleeve": {
    "direct_equity_holdings": [
      {
        "scheme_name": "RELIANCE INDUSTRIES LTD",
        "asset_class": "equity",
        "valuation": "450000",
        "amc": "EQUITY"
      }
    ],
    "equity_oriented_funds": [
      {
        "scheme_name": "HDFC Flexi Cap Fund",
        "asset_class": "mutual_fund",
        "valuation": "320000"
      }
    ],
    "counts": {
      "direct_equity": 8,
      "equity_oriented_funds": 4,
      "all_holdings": 22
    }
  },
  "preanalysis": {
    "portfolio_snapshot": {
      "number_of_holdings": 22,
      "total_invested_value": "2100000"
    },
    "concentration": {
      "largest_holding_percent": "18.50",
      "top5_percent": "52.00"
    },
    "sector_allocation": [
      { "sector": "Financials", "weight_percent": "28.0" }
    ],
    "style_allocation": [
      { "style": "large_cap", "weight_percent": "55.0" }
    ],
    "portfolio_flags": {
      "high_single_holding_concentration": true
    },
    "financial_health": {
      "emergency_months_cover": "4.5"
    },
    "holding_metrics": [],
    "data_gaps": [],
    "overlap": {},
    "insight_cards": []
  },
  "market_data": {
    "included": false,
    "note": "Live market prices intentionally omitted for this equity review agent."
  }
}
```

**Kinds of financial info in this payload:**

| Bucket | Examples |
|--------|----------|
| Behaviour | Psychometric risk / loss-aversion / capacity |
| Goals | Name, target ₹, date |
| Cash flow | Liquid, income, expenses |
| Holdings | Names, valuations, equity vs MF sleeve |
| Analytics (rules) | Concentration %, sector/style mix, flags, emergency cover |
| Knowledge | Separate `KNOWLEDGE_SNIPPETS` array (skill / evidence text) |

### 2.3 Output JSON the LLM must return

```json
{
  "observations": [
    "Largest holding is about 18.5% of invested value — single-name weight is elevated.",
    "Financials tilt is ~28% of mapped sector exposure."
  ],
  "risks": [
    "High single-name concentration can amplify drawdowns if that name sells off."
  ],
  "tradeoffs": [
    "Trimming concentration may reduce risk but also dilute a high-conviction name."
  ],
  "decision": "Review concentration and sector tilt before adding more to the largest equity name.",
  "recommended_actions": [
    "Pause topping up the overweight name until Twin concentration is below your comfort band.",
    "Review diversifying toward underrepresented sectors already flagged in preanalysis."
  ],
  "assumptions": [
    "Holdings and weights come from Twin/CAS preanalysis, not live prices."
  ],
  "missing_information": [
    "No live quotes — valuation is last CAS value."
  ],
  "confidence": "low",
  "key_factors": [
    "Concentration",
    "Goal horizon"
  ],
  "knowledge_used": [
    {
      "source": "skill",
      "section": "nism-investment-adviser-l1",
      "content": "Suitability before product discussion."
    }
  ]
}
```

### 2.4 How that becomes the Decision UI

The coordinator maps LLM text into `AnalysisResult`, then merges **rule-based** dashboard fields (portfolio health score, true exposure, worries, etc.). Final API body is a `DecisionResult` (see §4).

---

## 3. Use B — What-if / Counterfactuals

**Objective:** `explore_counterfactuals` (also attached on normal Decisions when data exists).

Two layers:

1. **Rules** — `apps/api/ai_cio/services/counterfactuals.py` → `build_counterfactuals()`  
2. **AI narrative** — `apps/api/ai_cio/services/counterfactual_ai.py` → `enrich_counterfactuals_with_ai()`  

Numbers are **never** recomputed by the LLM.

### 3.1 Scenario types (rules — no LLM)

| Id / kind | Question (conceptually) |
|-----------|-------------------------|
| `trim_vs_hold_largest` | Trim ~20% of largest holding vs hold |
| `contribution_forward` | Change monthly SIP by ±₹5k / ₹10k |
| Return / path variants | Alternate assumed returns or snapshot paths |
| Tax / emergency variants | When tax lots / liquid cover data exist |

### 3.2 Deterministic scenario JSON (example)

```json
{
  "id": "trim_vs_hold_largest",
  "kind": "recommendation_replay",
  "title": "What if you trim the largest holding vs hold?",
  "question": "Largest holding is ~18.50% of portfolio. Compare HOLD vs trimming 20% of that position.",
  "actual": {
    "label": "HOLD",
    "largest_holding_percent": "18.50",
    "portfolio_value": "2100000.00",
    "cash_freed": "0.00",
    "illustrative_tax_impact": "0.00",
    "summary": "Keep current concentration; no realization event."
  },
  "alternatives": [
    {
      "label": "TRIM 20% of largest holding",
      "largest_holding_percent": "14.80",
      "portfolio_value": "2100000.00",
      "cash_freed": "77700.00",
      "illustrative_tax_impact": null,
      "summary": "Reduce largest weight from 18.50% toward 14.80% by freeing ~₹77700."
    }
  ],
  "deltas": {
    "largest_holding_percent_change": "-3.70",
    "cash_freed": "77700.00",
    "illustrative_tax_impact": null
  },
  "assumptions": [
    "Trim size is illustrative (default 20% of largest holding value).",
    "Not a trade instruction or tax advice."
  ],
  "confidence": "low"
}
```

Full rules payload wrapper:

```json
{
  "available": true,
  "scenarios": [ "…as above…" ],
  "schema_note": "Deterministic only"
}
```

### 3.3 Input JSON to the What-if LLM

The AI does **not** get raw Twin holdings. It gets a **brief of already-computed scenarios** plus light Twin/decision context:

```json
{
  "decision_summary": "Compare current path vs alternate what-if paths…",
  "psychometric_risk_score": 55,
  "behaviour_divergences": [
    {
      "title": "Declared conservative vs equity-heavy book",
      "summary": "Psychometrics lean cautious; equity sleeve is large."
    }
  ],
  "top_worries": [
    {
      "title": "Concentration",
      "severity": "high",
      "detail": "Largest holding ~18.5%."
    }
  ],
  "recommended_actions": [
    "Review concentration before adding to largest name."
  ],
  "deterministic_scenarios": [
    {
      "id": "trim_vs_hold_largest",
      "kind": "recommendation_replay",
      "title": "What if you trim the largest holding vs hold?",
      "question": "Largest holding is ~18.50%…",
      "actual_label": "HOLD",
      "actual_summary": "Keep current concentration…",
      "deltas": {
        "largest_holding_percent_change": "-3.70",
        "cash_freed": "77700.00"
      },
      "alternatives": [
        {
          "label": "TRIM 20% of largest holding",
          "summary": "Reduce largest weight…",
          "cash_freed": "77700.00",
          "largest_holding_percent": "14.80"
        }
      ],
      "assumptions": ["Trim size is illustrative…"],
      "confidence": "low"
    }
  ]
}
```

### 3.4 Output JSON the What-if LLM must return

```json
{
  "cio_narrative": "Across scenarios, concentration and contribution path matter more than return tweaks for this Twin.",
  "priority_focus": "Study trim_vs_hold_largest first — largest weight is elevated versus a mid risk score.",
  "tradeoff_insight": "Trimming frees cash and lowers single-name risk but may realize tax and reduce upside in that name.",
  "suggested_next_review": "Re-check Twin concentration and emergency cash after any hypothetical trim — do not place a trade from this screen.",
  "scenarios": [
    {
      "id": "trim_vs_hold_largest",
      "priority_rank": 1,
      "explanation": "Given ~18.5% in one name, the trim path shows how concentration and cash change without inventing new prices.",
      "why_it_matters": "Matches your concentration worry and mid risk profile."
    }
  ]
}
```

### 3.5 Merged What-if payload (API / UI)

```json
{
  "available": true,
  "scenarios": [
    {
      "id": "trim_vs_hold_largest",
      "title": "What if you trim the largest holding vs hold?",
      "actual": { "label": "HOLD", "largest_holding_percent": "18.50" },
      "alternatives": [{ "label": "TRIM 20%…", "cash_freed": "77700.00" }],
      "ai_explanation": "Given ~18.5% in one name…",
      "ai_why_it_matters": "Matches your concentration worry…",
      "ai_priority_rank": 1
    }
  ],
  "ai": {
    "used": true,
    "cio_narrative": "Across scenarios…",
    "priority_focus": "Study trim_vs_hold_largest first…",
    "tradeoff_insight": "Trimming frees cash…",
    "suggested_next_review": "Re-check Twin concentration…",
    "model_note": "AI explained and ranked rule-based scenarios. It did not recompute portfolio maths or invent holdings."
  }
}
```

UI tags: **Rules** on numbers, **AI** on narrative blocks.  
Focused What-if mode (`objective === explore_counterfactuals`) shows mainly this panel.

---

## 4. Full DecisionResult (what the UI consumes)

After all stages, `run_decision()` returns roughly:

```json
{
  "decision_id": "…",
  "user_id": 1,
  "objective": "review_equity_portfolio",
  "decision": "One-line CIO decision text",
  "confidence": "low",
  "rationale": ["…"],
  "risks": ["…"],
  "tradeoffs": ["…"],
  "assumptions": ["…"],
  "recommended_actions": ["…"],
  "portfolio_health": {},
  "top_worries": [],
  "concentration_analysis": {},
  "true_exposure": {},
  "tax_intelligence": { "available": true, "agent": "tax_agent" },
  "fd_intelligence": { "available": true, "agent": "fd_agent" },
  "trajectory_intelligence": { "available": true },
  "decision_trace": {},
  "agent_perspectives": { "agents": [], "disagreements": [] },
  "behavioral_intelligence": {},
  "data_quality": {},
  "counterfactuals": { "available": true, "scenarios": [], "ai": {} },
  "execution": {
    "stages": ["build_context", "analyze", "tax_agent", "fd_agent", "…"],
    "analyzer": "EquityAgentAnalyzer",
    "agent": "EquityAgentAnalyzer",
    "focus": "equity"
  }
}
```

**Tax / FD** are specialist engines (deterministic). They are **not** the Equity LLM payload; their outputs are attached for the Trace / UI.

---

## 5. Quick compare: Decision LLM vs What-if LLM

| | Decision (Equity Agent) | What-if AI |
|--|-------------------------|------------|
| **Job** | Suitability-style equity review | Explain / rank ready-made scenarios |
| **Gets** | Twin equity sleeve + preanalysis + skills | Scenario briefs + risk score + worries |
| **Must not** | Invent prices / holdings / buy orders | Recompute ₹ or invent new scenarios |
| **Returns** | observations, risks, actions, decision | cio_narrative, priority, per-scenario explanation |
| **Numbers source** | Twin / rules (LLM cites them) | Rules only (`counterfactuals.py`) |

---

## 6. Related code map

| Piece | Path |
|-------|------|
| Orchestrator | `apps/api/ai_cio/services/orchestration/coordinator.py` |
| Equity LLM agent | `apps/api/ai_cio/services/agents/equity_agent.py` |
| LLM client | `apps/api/ai_cio/services/agents/openrouter_client.py` |
| Skills loader | `apps/api/ai_cio/services/agents/skills_loader.py` |
| What-if maths | `apps/api/ai_cio/services/counterfactuals.py` |
| What-if AI | `apps/api/ai_cio/services/counterfactual_ai.py` |
| Contracts | `apps/api/domain/decision/contracts.py` |
| Demo dump (Aryaman) | `docs/ARYAMAN_DECISION_PIPELINE.md` |

---

## 7. One-liner for reviews

> Decisions feed the LLM a **structured Twin + preanalysis JSON** (behaviour, goals, cash, holdings, concentration). What-if first **computes scenarios with rules**, then feeds the LLM only those **scenario briefs** so it can narrate and rank — maths stay outside the model.
