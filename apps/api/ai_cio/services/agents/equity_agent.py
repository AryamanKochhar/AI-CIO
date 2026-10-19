"""Equity-focused decision agent (Ling via OpenRouter).

Uses Twin behaviour/goals/portfolio + deterministic preanalysis + domain skills.
Returns AnalysisResult shaped for the Decisions orchestration UI.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from domain.decision.capabilities import Capability
from domain.decision.contracts import (
    AnalysisResult,
    Evidence,
    InvestmentContext,
    InvestmentStrategy,
)
from ai_cio.services.agents.decision_insights import build_detailed_insights
from ai_cio.services.agents.portfolio_dashboard import build_portfolio_dashboard
from ai_cio.services.agents.openrouter_client import (
    OpenRouterError,
    chat_completion,
    extract_json_object,
)
from ai_cio.services.agents.skills_loader import (
    EQUITY_AGENT_SKILL_NAMES,
    load_domain_skills,
    skill_evidence_stubs,
)
from ai_cio.services.instruments import DomainError
from ai_cio.services.twin_analytics import build_portfolio_preanalysis
from ai_cio.services.trendlyne_sectors import fetch_sector_day_changes
from ai_cio.services.finance_standards import (
    build_finance_review_context,
    resolve_model_knowledge_claims,
)

logger = logging.getLogger(__name__)


class _JsonEncoder(json.JSONEncoder):
    def default(self, o):  # noqa: ANN001
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def _equity_payload(twin: dict[str, Any], preanalysis: dict[str, Any] | None) -> dict[str, Any]:
    portfolio = twin.get("portfolio") or {}
    holdings = portfolio.get("holdings") or []
    equity_holdings = [
        h
        for h in holdings
        if h.get("asset_class") == "equity" or h.get("amc") == "EQUITY"
    ]
    # Equity-oriented MFs (heuristic by name) — still labeled as mutual_fund
    equity_like_funds = [
        h
        for h in holdings
        if h not in equity_holdings
        and any(
            token in (h.get("scheme_name") or "").lower()
            for token in ("equity", "elss", "midcap", "small cap", "smallcap", "large cap", "index", "nifty")
        )
    ]
    pa = preanalysis or twin.get("preanalysis") or {}
    holding_metrics = pa.get("holding_metrics") or []
    equity_metrics = [m for m in holding_metrics if m.get("instrument_type") == "direct_equity"]
    detailed = build_detailed_insights(twin=twin, preanalysis=pa, objective="review_equity_portfolio")
    sector_day = fetch_sector_day_changes() if holdings else {"available": False, "reason": "no_holdings_in_scope"}
    market_data: dict[str, Any] = {
        "included": bool(sector_day.get("available")),
        "live_prices_included": False,
        "note": (
            "Sector day-change % from Trendlyne when available. "
            "Live stock prices intentionally omitted."
        ),
        "sector_day_changes": sector_day,
    }
    return {
        "user": twin.get("user"),
        "behaviour": twin.get("behaviour"),
        "goals": twin.get("goals"),
        "financial_position": twin.get("financial_position"),
        "completeness": twin.get("completeness"),
        "finance_review_context": build_finance_review_context(twin, EQUITY_AGENT_SKILL_NAMES),
        "equity_sleeve": {
            "direct_equity_holdings": equity_holdings,
            "equity_oriented_funds": equity_like_funds,
            "counts": {
                "direct_equity": len(equity_holdings),
                "equity_oriented_funds": len(equity_like_funds),
                "all_holdings": len(holdings),
            },
        },
        "preanalysis": {
            "portfolio_snapshot": pa.get("portfolio_snapshot"),
            "concentration": pa.get("concentration"),
            "sector_allocation": detailed.get("sector_allocation") or pa.get("sector_allocation"),
            "style_allocation": detailed.get("style_allocation"),
            "insight_cards": detailed.get("insight_cards"),
            "holding_metrics": equity_metrics
            or [m for m in holding_metrics if m.get("instrument_type") == "mutual_fund"][:15],
            "portfolio_flags": pa.get("portfolio_flags"),
            "financial_health": pa.get("financial_health"),
            "goals": pa.get("goals"),
            "data_gaps": pa.get("data_gaps"),
            "overlap": pa.get("overlap"),
        },
        "market_data": market_data,
    }


def _fallback_from_preanalysis(preanalysis: dict[str, Any]) -> dict[str, list[str]]:
    """Deterministic observations/actions if the model returns empty fields."""
    observations: list[str] = []
    actions: list[str] = []
    risks: list[str] = []
    snap = preanalysis.get("portfolio_snapshot") or {}
    conc = preanalysis.get("concentration") or {}
    flags = preanalysis.get("portfolio_flags") or {}
    health = preanalysis.get("financial_health") or {}

    n = snap.get("number_of_holdings")
    if n:
        observations.append(f"Portfolio preanalysis shows {n} holdings in scope.")
    if conc.get("largest_holding_percent"):
        observations.append(
            f"Largest holding weight is {conc['largest_holding_percent']}% of invested value."
        )
    if flags.get("high_single_holding_concentration"):
        observations.append("Flag: high single-holding concentration relative to configured threshold.")
        actions.append("Review whether the largest holding size fits your equity risk and goals.")
    if flags.get("high_single_stock_concentration"):
        observations.append("Flag: a single direct equity name is a large share of the portfolio.")
        actions.append("Review single-stock concentration and whether to trim or diversify within equity.")
    if flags.get("missing_goals"):
        observations.append("Goals are missing — equity suitability vs horizon cannot be fully assessed.")
        actions.append("Add goal timelines before changing equity allocation aggressively.")
    if flags.get("missing_finances"):
        observations.append("Income/expenses/liquid cash are missing — risk capacity is incomplete.")
        actions.append("Complete finances (income, expenses, liquid buffer) to judge equity risk capacity.")
    if health.get("liquid_assets_to_monthly_expenses"):
        observations.append(
            f"Liquidity cover is about {health['liquid_assets_to_monthly_expenses']} months of expenses."
        )
    if not actions:
        actions.append("Review equity sleeve diversification and concentration using the holding weights provided.")
    if not risks:
        risks.append("Acting on incomplete Twin data may misjudge equity suitability.")
    return {
        "observations": observations,
        "recommended_actions": actions,
        "risks": risks,
        "tradeoffs": [
            "Concentrated equity can amplify gains and losses; broader equity diversification may reduce single-name risk but dilute high-conviction positions."
        ],
    }


def _system_prompt(skills: str) -> str:
    return f"""You are the AI-CIO Equity Portfolio Decision Agent (India-focused).

Specialize in EQUITY only: direct equity and equity-oriented funds.
Use behaviour, goals, holdings weights, preanalysis flags, and market_data.sector_day_changes when present.

Rules:
- Suitability first. Never invent prices, sectors, holdings, or day-change %.
- If market_data.sector_day_changes.available is true, describe only its supplied as-of period
  and actual Twin exposure overlap. Availability alone does not establish freshness; never
  label cached or undated context as today's market.
- Treat sector day changes as short-term market context only — not a reason to buy/sell tickers.
- No ticker buy/sell orders; category / concentration / diversification review only.
- No guaranteed returns.
- Follow finance_review_context.review_structure: observed facts -> why they matter ->
  conditional review options -> trade-offs -> specific next action -> sources and missing data.
- Separate risk willingness, financial loss capacity and goal need. Never infer them from age,
  occupation, household labels or a synthetic persona. Unknown facts stay unknown.
- Use only the supplied deterministic numbers. Do not compute new returns, taxes, target
  allocations, insurance coverage or probabilities. Context sources are not legal rate tables.
- Arrays may be empty when evidence is absent. Never invent a second item or a portfolio fact
  to fill a response. Include finance_review_context.required_missing_information even if it
  limits the conclusion. No holdings means no observed stock/sector concentration claim.
- Sector changes, books and framework summaries do not establish suitability. Discuss costs,
  liquidity and tax limitations before any allocation-change review; no trade instructions.
- A stale source is context requiring renewed verification, not current legal authority.
- Cite only source_id values supplied in finance_review_context.source_context. Never invent
  URLs, page numbers, publisher claims or source IDs. Loaded material is not proof it was applied.

Return ONLY JSON:
{{
  "observations": ["An observed input or deterministic result, with source/date where provided"],
  "risks": ["Why an observed fact matters for a recorded goal or constraint"],
  "tradeoffs": ["Conditional review options and their liquidity, cost, risk or tax tensions"],
  "decision": "One clear decision summary for human review.",
  "recommended_actions": [
    "Specific next review step: identify the input or page to inspect, why, and what remains unknown"
  ],
  "assumptions": ["..."],
  "missing_information": ["..."],
  "confidence": "low",
  "key_factors": ["...", "..."],
  "knowledge_used": [{{"source_id": "an ID actually supplied in source_context"}}]
}}

Be specific only where the payload supports it. Label facts, educational interpretation,
assumptions and not-evaluated items distinctly. A useful action can be confirming a goal date,
checking exposure records or reviewing tax lots; it need not imply a transaction.

Skills:
{skills}
"""


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


class EquityAgentAnalyzer:
    """DecisionAnalyzer implementation for equity portfolio review."""

    name = "EquityAgentAnalyzer"

    def analyze(
        self,
        context: InvestmentContext,
        *,
        capabilities: list[Capability],
    ) -> AnalysisResult:
        twin = context.twin
        preanalysis = twin.get("preanalysis") if isinstance(twin.get("preanalysis"), dict) else {}

        skills = load_domain_skills(EQUITY_AGENT_SKILL_NAMES, max_chars_per_skill=2800)
        if not skills:
            raise DomainError("Domain skills (.cursor/skills) are missing; cannot run equity agent.")

        payload = _equity_payload(twin, preanalysis)
        knowledge_bits = [
            {
                "source": e.source,
                "section": e.section,
                "reference": e.reference,
                "content": e.content,
            }
            for e in context.knowledge_evidence
        ]
        user_msg = (
            "Produce an equity-focused decision for this user. "
            "Use only supported findings; empty arrays are valid when evidence is absent. "
            "Respond with JSON only.\n\n"
            f"OBJECTIVE: {context.objective.value}\n\n"
            f"TWIN_EQUITY_PAYLOAD:\n```json\n{json.dumps(payload, cls=_JsonEncoder, indent=2)}\n```\n\n"
            f"KNOWLEDGE_SNIPPETS:\n```json\n{json.dumps(knowledge_bits, indent=2)}\n```"
        )
        messages = [
            {"role": "system", "content": _system_prompt(skills)},
            {"role": "user", "content": user_msg},
        ]

        try:
            # An equity review without holdings cannot support stock/sector claims.
            # Keep the explicit missing-data result and do not spend a model call.
            raw = chat_completion(messages) if (twin.get("portfolio") or {}).get("holdings") else "{}"
            data = extract_json_object(raw)
        except OpenRouterError as exc:
            logger.exception("equity_agent_failed; falling back to rule-based analyzer")
            from ai_cio.services.orchestration.analyzers.simple_allocator import SimpleAllocatorAnalyzer

            fallback = SimpleAllocatorAnalyzer().analyze(context, capabilities=capabilities)
            # Keep equity dashboard metrics even when LLM fails.
            fb = build_portfolio_dashboard(
                twin=twin,
                preanalysis=preanalysis,
                objective=context.objective.value,
            )
            fallback.portfolio_health = dict(fb.get("portfolio_health") or fallback.portfolio_health or {})
            fallback.insight_cards = list(fb.get("insight_cards") or fallback.insight_cards or [])
            fallback.style_allocation = list(fb.get("style_allocation") or fallback.style_allocation or [])
            fallback.sector_allocation = list(fb.get("sector_allocation") or fallback.sector_allocation or [])
            fallback.top_worries = list(fb.get("top_worries") or fallback.top_worries or [])
            fallback.concentration_analysis = dict(
                fb.get("concentration_analysis") or fallback.concentration_analysis or {}
            )
            fallback.true_exposure = dict(fb.get("true_exposure") or fallback.true_exposure or {})
            fallback.quality_valuation = dict(fb.get("quality_valuation") or fallback.quality_valuation or {})
            assumptions = list(fallback.assumptions or [])
            assumptions.append(
                f"Equity LLM unavailable ({exc}); used rule-based equity dashboard instead."
            )
            fallback.assumptions = assumptions
            fallback.missing_information = list(dict.fromkeys(
                list(fallback.missing_information or [])
                + payload["finance_review_context"]["required_missing_information"]
            ))
            return fallback

        observations = _as_str_list(data.get("observations"))
        risks = _as_str_list(data.get("risks"))
        tradeoffs = _as_str_list(data.get("tradeoffs"))
        actions = _as_str_list(data.get("recommended_actions"))
        assumptions = _as_str_list(data.get("assumptions"))
        missing = _as_str_list(data.get("missing_information"))
        review_context = payload["finance_review_context"]
        missing = list(dict.fromkeys(missing + review_context["required_missing_information"]))
        key_factors = _as_str_list(data.get("key_factors"))
        decision_summary = data.get("decision") if isinstance(data.get("decision"), str) else None
        if decision_summary:
            decision_summary = decision_summary.strip()

        if not observations or not actions:
            fb = build_portfolio_dashboard(
                twin=twin,
                preanalysis=preanalysis,
                objective=context.objective.value,
            )
            if not observations:
                observations = list(fb.get("observations") or [])
            if not actions:
                actions = list(fb.get("recommended_actions") or [])
            if not risks:
                risks = list(fb.get("risks") or [])
            if not tradeoffs:
                tradeoffs = list(fb.get("tradeoffs") or [])
            if not decision_summary:
                decision_summary = fb.get("decision_summary")
            insight_cards = list(fb.get("insight_cards") or [])
            style_allocation = list(fb.get("style_allocation") or [])
            sector_allocation = list(fb.get("sector_allocation") or [])
        else:
            fb = build_portfolio_dashboard(
                twin=twin,
                preanalysis=preanalysis,
                objective=context.objective.value,
            )
            insight_cards = list(fb.get("insight_cards") or [])
            style_allocation = list(fb.get("style_allocation") or [])
            sector_allocation = list(fb.get("sector_allocation") or [])
            for line in fb.get("observations") or []:
                if line not in observations:
                    observations.append(line)
            for line in fb.get("recommended_actions") or []:
                if line not in actions:
                    actions.append(line)

        evidence: list[Evidence] = list(context.knowledge_evidence)
        if not (twin.get("portfolio") or {}).get("holdings"):
            decision_summary = "Complete portfolio records and goal context before an equity allocation review."
        for stub in skill_evidence_stubs(EQUITY_AGENT_SKILL_NAMES):
            evidence.append(
                Evidence(
                    source=stub["source"],
                    section=stub["section"],
                    reference=stub["reference"],
                    content=stub["content"],
                    relevance=stub.get("relevance") or "skill",
                )
            )
        for item in resolve_model_knowledge_claims(data.get("knowledge_used"), review_context["source_context"]):
            evidence.append(
                Evidence(
                    source=item["source"],
                    section=item["section"],
                    reference=item["reference"],
                    content=item["content"],
                    relevance=item["relevance"],
                )
            )

        strategy = InvestmentStrategy(
            name="Equity portfolio review",
            allocation={},
            rationale=actions or observations[:3],
            assumptions=assumptions,
            expected_characteristics={
                "focus": "equity",
                "agent": self.name,
                "confidence": (
                    "low" if len(review_context["known_amount_fields"]) < 3
                    or not (twin.get("portfolio") or {}).get("holdings")
                    or review_context["declared_willingness_status"] == "unknown"
                    or not (twin.get("goals") or {}).get("items")
                    else "medium" if str(data.get("confidence")) in {"medium", "high"} else "low"
                ),
                "review_standard": review_context["version"],
            },
            risks=risks,
            evidence=evidence[:8],
        )

        if key_factors and not assumptions:
            assumptions = [f"Factor: {f}" for f in key_factors[:5]]

        return AnalysisResult(
            observations=observations,
            candidate_strategies=[strategy],
            risks=risks,
            tradeoffs=tradeoffs,
            assumptions=assumptions,
            evidence=evidence,
            missing_information=missing,
            capabilities_used=[cap.value for cap in capabilities],
            decision_summary=decision_summary
            or "Review the equity observations and recommended actions below.",
            recommended_actions=actions,
            insight_cards=insight_cards,
            style_allocation=style_allocation,
            sector_allocation=sector_allocation,
            portfolio_health=dict(fb.get("portfolio_health") or {}),
            top_worries=list(fb.get("top_worries") or []),
            concentration_analysis=dict(fb.get("concentration_analysis") or {}),
            true_exposure=dict(fb.get("true_exposure") or {}),
            quality_valuation=dict(fb.get("quality_valuation") or {}),
        )


def ensure_preanalysis_on_twin(db, twin: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Attach preanalysis to twin dict if missing (used by adapters/tests)."""
    existing = twin.get("preanalysis")
    if isinstance(existing, dict) and existing.get("schema_version"):
        return twin
    twin = dict(twin)
    twin["preanalysis"] = build_portfolio_preanalysis(db, user_id)
    return twin
