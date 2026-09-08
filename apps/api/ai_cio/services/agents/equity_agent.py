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
    return {
        "user": twin.get("user"),
        "behaviour": twin.get("behaviour"),
        "goals": twin.get("goals"),
        "financial_position": twin.get("financial_position"),
        "completeness": twin.get("completeness"),
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
        "market_data": {
            "included": False,
            "note": "Live market prices intentionally omitted for this equity review agent.",
        },
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
Use behaviour, goals, holdings weights, and preanalysis flags.

Rules:
- Suitability first. Never invent prices, sectors, or holdings.
- No ticker buy/sell orders; category / concentration / diversification review only.
- No guaranteed returns.
- Every array below MUST have at least 2 concrete items grounded in the payload.

Return ONLY JSON:
{{
  "observations": ["fact-based observation including % weights / tilts", "..."],
  "risks": ["...", "..."],
  "tradeoffs": ["...", "..."],
  "decision": "One clear decision summary for human review.",
  "recommended_actions": [
    "Concrete review action e.g. reduce topping up overweight sector X; consider diversifying toward underrepresented sector/style Y",
    "..."
  ],
  "assumptions": ["..."],
  "missing_information": ["..."],
  "confidence": "low",
  "key_factors": ["...", "..."],
  "knowledge_used": [{{"source": "skill", "section": "name", "content": "how it informed you"}}]
}}

Be specific: cite holding weights, style tilts (mid/small/large), AMC concentration, and sector tilts when present in the payload. Prefer "review diversifying toward X because overweight Y" language — not ticker buy orders.

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
            "Fill every required JSON array with concrete items from the payload. "
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
            raw = chat_completion(messages)
            data = extract_json_object(raw)
        except OpenRouterError as exc:
            logger.exception("equity_agent_failed")
            raise DomainError(str(exc)) from exc

        observations = _as_str_list(data.get("observations"))
        risks = _as_str_list(data.get("risks"))
        tradeoffs = _as_str_list(data.get("tradeoffs"))
        actions = _as_str_list(data.get("recommended_actions"))
        assumptions = _as_str_list(data.get("assumptions"))
        missing = _as_str_list(data.get("missing_information"))
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
        for item in data.get("knowledge_used") or []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            evidence.append(
                Evidence(
                    source=str(item.get("source") or "equity_agent"),
                    section=str(item.get("section") or "knowledge_used"),
                    reference="model_cited",
                    content=content.strip()[:600],
                    relevance="cited_by_equity_agent",
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
                "confidence": str(data.get("confidence") or "low"),
            },
            risks=risks,
            evidence=evidence[:8],
        )

        if key_factors and not assumptions:
            assumptions = [f"Factor: {f}" for f in key_factors[:5]]

        return AnalysisResult(
            observations=observations or ["Equity agent completed with limited observations."],
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
