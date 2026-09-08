"""First decision analyzer: rules + detailed Twin/preanalysis insights."""

from __future__ import annotations

from decimal import Decimal

from domain.decision.capabilities import Capability
from domain.decision.contracts import (
    AnalysisResult,
    DecisionObjective,
    Evidence,
    InvestmentContext,
    InvestmentStrategy,
)
from ai_cio.services.agents.portfolio_dashboard import build_portfolio_dashboard


class SimpleAllocatorAnalyzer:
    def analyze(
        self,
        context: InvestmentContext,
        *,
        capabilities: list[Capability],
    ) -> AnalysisResult:
        dashboard = build_portfolio_dashboard(
            twin=context.twin,
            preanalysis=context.twin.get("preanalysis") if isinstance(context.twin.get("preanalysis"), dict) else {},
            objective=context.objective.value,
        )
        insights = {
            "observations": dashboard.get("observations") or [],
            "recommended_actions": dashboard.get("recommended_actions") or [],
            "risks": dashboard.get("risks") or [],
            "tradeoffs": dashboard.get("tradeoffs") or [],
            "decision_summary": dashboard.get("decision_summary"),
            "insight_cards": dashboard.get("insight_cards") or [],
            "style_allocation": dashboard.get("style_allocation") or [],
            "sector_allocation": dashboard.get("sector_allocation") or [],
            "portfolio_health": dashboard.get("portfolio_health") or {},
            "top_worries": dashboard.get("top_worries") or [],
            "concentration_analysis": dashboard.get("concentration_analysis") or {},
            "true_exposure": dashboard.get("true_exposure") or {},
            "quality_valuation": dashboard.get("quality_valuation") or {},
        }
        if context.objective == DecisionObjective.ALLOCATE_CAPITAL:
            return self._allocate_capital(context, capabilities, insights)
        if context.objective == DecisionObjective.REVIEW_PORTFOLIO:
            return self._review_portfolio(context, capabilities, insights)
        if context.objective == DecisionObjective.EVALUATE_PORTFOLIO_RISK:
            return self._evaluate_risk(context, capabilities, insights)
        if context.objective == DecisionObjective.REVIEW_EQUITY_PORTFOLIO:
            return self._review_equity(context, capabilities, insights)
        return self._generic(context, capabilities, insights)

    def _merge(
        self,
        *,
        context: InvestmentContext,
        capabilities: list[Capability],
        insights: dict,
        strategies: list[InvestmentStrategy],
        extra_observations: list[str] | None = None,
        extra_assumptions: list[str] | None = None,
    ) -> AnalysisResult:
        observations = list(insights.get("observations") or [])
        if extra_observations:
            observations = extra_observations + observations
        return AnalysisResult(
            observations=observations,
            candidate_strategies=strategies,
            risks=list(insights.get("risks") or []),
            tradeoffs=list(insights.get("tradeoffs") or []),
            assumptions=list(extra_assumptions or [])
            + [
                "Insights use Twin holdings + preanalysis metrics; style/sector labels may be name heuristics.",
                "Educational review only — not a buy/sell instruction.",
            ],
            evidence=list(context.knowledge_evidence),
            missing_information=list(context.missing_optional),
            capabilities_used=[cap.value for cap in capabilities],
            decision_summary=insights.get("decision_summary"),
            recommended_actions=list(insights.get("recommended_actions") or []),
            insight_cards=list(insights.get("insight_cards") or []),
            style_allocation=list(insights.get("style_allocation") or []),
            sector_allocation=list(insights.get("sector_allocation") or []),
            portfolio_health=dict(insights.get("portfolio_health") or {}),
            top_worries=list(insights.get("top_worries") or []),
            concentration_analysis=dict(insights.get("concentration_analysis") or {}),
            true_exposure=dict(insights.get("true_exposure") or {}),
            quality_valuation=dict(insights.get("quality_valuation") or {}),
        )

    def _allocate_capital(
        self,
        context: InvestmentContext,
        capabilities: list[Capability],
        insights: dict,
    ) -> AnalysisResult:
        capital = context.decision_parameters.get("available_capital")
        if capital is None:
            capital = Decimal("0")

        goals = (context.twin.get("goals") or {}).get("items") or []
        short_horizon = any((g.get("horizon_years") or 99) <= 3 for g in goals)

        if short_horizon:
            conservative_split = {"cash": Decimal("0.50"), "debt": Decimal("0.35"), "equity": Decimal("0.15")}
            balanced_split = {"cash": Decimal("0.35"), "debt": Decimal("0.40"), "equity": Decimal("0.25")}
        else:
            conservative_split = {"cash": Decimal("0.40"), "debt": Decimal("0.40"), "equity": Decimal("0.20")}
            balanced_split = {"cash": Decimal("0.20"), "debt": Decimal("0.30"), "equity": Decimal("0.50")}

        evidence = list(context.knowledge_evidence)
        actions = list(insights.get("recommended_actions") or [])
        action_note = actions[0] if actions else "Prefer filling diversification gaps with new capital."
        strategies = [
            self._make_strategy(
                name="Conservative",
                split=conservative_split,
                capital=capital,
                evidence=evidence,
                note="Keeps more in cash and debt for stability.",
                extra_rationale=[action_note],
            ),
            self._make_strategy(
                name="Balanced",
                split=balanced_split,
                capital=capital,
                evidence=evidence,
                note="Mixes growth and stability; still avoid topping up already-heavy holdings.",
                extra_rationale=[action_note],
            ),
        ]

        extra = [
            f"Reviewing how to allocate {capital} of new capital across cash, debt, and equity.",
            "New money should prefer underrepresented sleeves, not the already-largest holding.",
        ]
        return self._merge(
            context=context,
            capabilities=capabilities,
            insights=insights,
            strategies=strategies,
            extra_observations=extra,
        )

    def _review_portfolio(self, context, capabilities, insights) -> AnalysisResult:
        portfolio = context.twin.get("portfolio") or {}
        holdings_count = portfolio.get("holdings_count") or 0
        return self._merge(
            context=context,
            capabilities=capabilities,
            insights=insights,
            strategies=[],
            extra_observations=[
                f"Portfolio has {holdings_count} holding(s) on record.",
                "Review focuses on concentration, style/sector balance, and goal fit — not return promises.",
            ],
        )

    def _evaluate_risk(self, context, capabilities, insights) -> AnalysisResult:
        behaviour = context.twin.get("behaviour") or {}
        extra = [
            "Risk review combines willingness (psychometrics), capacity (finances), and portfolio concentration/tilts.",
        ]
        if behaviour.get("status") != "known":
            extra.append("Psychometric profile is missing; willingness is unknown.")
        return self._merge(
            context=context,
            capabilities=capabilities,
            insights=insights,
            strategies=[],
            extra_observations=extra,
        )

    def _review_equity(self, context, capabilities, insights) -> AnalysisResult:
        return self._merge(
            context=context,
            capabilities=capabilities,
            insights=insights,
            strategies=[
                InvestmentStrategy(
                    name="Equity portfolio review",
                    allocation={},
                    rationale=list(insights.get("recommended_actions") or [])[:5],
                    assumptions=["Equity-focused review using Twin + preanalysis."],
                    expected_characteristics={"focus": "equity", "agent": "SimpleAllocatorAnalyzer"},
                    risks=list(insights.get("risks") or [])[:3],
                    evidence=list(context.knowledge_evidence)[:3],
                )
            ],
            extra_observations=["Equity sleeve review (rule-based detailed insights)."],
        )

    def _generic(self, context, capabilities, insights) -> AnalysisResult:
        return self._merge(
            context=context,
            capabilities=capabilities,
            insights=insights,
            strategies=[],
            extra_observations=[f"Processed decision objective: {context.objective.value}."],
        )

    def _make_strategy(
        self,
        *,
        name: str,
        split: dict[str, Decimal],
        capital: Decimal,
        evidence: list[Evidence],
        note: str,
        extra_rationale: list[str] | None = None,
    ) -> InvestmentStrategy:
        allocation = {bucket: (capital * share).quantize(Decimal("0.01")) for bucket, share in split.items()}
        total = sum(allocation.values(), Decimal("0"))
        if total != capital:
            allocation["cash"] = allocation.get("cash", Decimal("0")) + (capital - total)

        rationale = [note, "Split by broad asset type for planning discussion."]
        if extra_rationale:
            rationale.extend(extra_rationale)

        return InvestmentStrategy(
            name=name,
            allocation=allocation,
            rationale=rationale,
            assumptions=["Amounts sum to the available capital requested."],
            expected_characteristics={
                "volatility": "lower" if name == "Conservative" else "moderate",
                "growth_potential": "moderate" if name == "Conservative" else "higher",
            },
            risks=["Values can move up or down; returns are not guaranteed."],
            evidence=evidence[:2],
        )
