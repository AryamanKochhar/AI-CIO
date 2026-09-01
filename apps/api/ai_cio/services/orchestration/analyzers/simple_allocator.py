"""First decision analyzer: simple rules, no AI required."""

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


class SimpleAllocatorAnalyzer:
    def analyze(
        self,
        context: InvestmentContext,
        *,
        capabilities: list[Capability],
    ) -> AnalysisResult:
        if context.objective == DecisionObjective.ALLOCATE_CAPITAL:
            return self._allocate_capital(context, capabilities)
        if context.objective == DecisionObjective.REVIEW_PORTFOLIO:
            return self._review_portfolio(context, capabilities)
        if context.objective == DecisionObjective.EVALUATE_PORTFOLIO_RISK:
            return self._evaluate_risk(context, capabilities)
        return self._generic(context, capabilities)

    def _allocate_capital(
        self,
        context: InvestmentContext,
        capabilities: list[Capability],
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
        strategies = [
            self._make_strategy(
                name="Conservative",
                split=conservative_split,
                capital=capital,
                evidence=evidence,
                note="Keeps more in cash and debt for stability.",
            ),
            self._make_strategy(
                name="Balanced",
                split=balanced_split,
                capital=capital,
                evidence=evidence,
                note="Mixes growth and stability.",
            ),
        ]

        missing = list(context.missing_optional)
        observations = [
            f"Reviewing how to allocate {capital} across cash, debt, and equity.",
            "Risk preference is only one input; goals and liquidity also matter.",
        ]
        if context.market_context.get("available"):
            observations.append("Current market context is included for awareness, not as a buy signal.")
        else:
            missing.append("market_data")
            observations.append("Market data was unavailable; allocation does not depend on live prices.")

        return AnalysisResult(
            observations=observations,
            candidate_strategies=strategies,
            risks=[
                "Equity can fall in the short term.",
                "Too much cash may reduce long-term growth.",
            ],
            tradeoffs=[
                "Higher equity may support long goals but adds volatility.",
                "Higher cash improves flexibility but may lag inflation.",
            ],
            assumptions=[
                "Allocation is by broad asset type, not specific products.",
                "This is educational structure, not a buy or sell instruction.",
            ],
            evidence=evidence,
            missing_information=missing,
            capabilities_used=[cap.value for cap in capabilities],
        )

    def _review_portfolio(self, context: InvestmentContext, capabilities: list[Capability]) -> AnalysisResult:
        portfolio = context.twin.get("portfolio") or {}
        holdings_count = portfolio.get("holdings_count") or 0
        observations = [
            f"Portfolio has {holdings_count} holding(s) on record.",
            "Review checks fit with goals and concentration, not performance promises.",
        ]
        return AnalysisResult(
            observations=observations,
            candidate_strategies=[],
            risks=["Concentration can increase loss if one holding falls."],
            tradeoffs=["Diversifying may reduce single-name risk but does not remove market risk."],
            assumptions=["Holdings come from uploaded statements and user data."],
            evidence=list(context.knowledge_evidence),
            missing_information=list(context.missing_optional),
            capabilities_used=[cap.value for cap in capabilities],
        )

    def _evaluate_risk(self, context: InvestmentContext, capabilities: list[Capability]) -> AnalysisResult:
        behaviour = context.twin.get("behaviour") or {}
        portfolio = context.twin.get("portfolio") or {}
        observations = [
            "Risk review looks at willingness, capacity, concentration, and liquidity together.",
        ]
        if behaviour.get("status") != "known":
            observations.append("Psychometric profile is missing; willingness is unknown.")
        if (portfolio.get("holdings_count") or 0) <= 3:
            observations.append("Portfolio appears concentrated.")

        return AnalysisResult(
            observations=observations,
            candidate_strategies=[],
            risks=["Risk cannot be reduced to a single score or allocation formula."],
            tradeoffs=[],
            assumptions=["This is a structured review, not a trading recommendation."],
            evidence=list(context.knowledge_evidence),
            missing_information=list(context.missing_optional),
            capabilities_used=[cap.value for cap in capabilities],
        )

    def _generic(self, context: InvestmentContext, capabilities: list[Capability]) -> AnalysisResult:
        return AnalysisResult(
            observations=[f"Processed decision objective: {context.objective.value}."],
            candidate_strategies=[],
            risks=[],
            tradeoffs=[],
            assumptions=[],
            evidence=list(context.knowledge_evidence),
            missing_information=list(context.missing_optional),
            capabilities_used=[cap.value for cap in capabilities],
        )

    def _make_strategy(
        self,
        *,
        name: str,
        split: dict[str, Decimal],
        capital: Decimal,
        evidence: list[Evidence],
        note: str,
    ) -> InvestmentStrategy:
        allocation = {bucket: (capital * share).quantize(Decimal("0.01")) for bucket, share in split.items()}
        total = sum(allocation.values(), Decimal("0"))
        if total != capital:
            allocation["cash"] = allocation.get("cash", Decimal("0")) + (capital - total)

        return InvestmentStrategy(
            name=name,
            allocation=allocation,
            rationale=[note, "Split by broad asset type for planning discussion."],
            assumptions=["Amounts sum to the available capital requested."],
            expected_characteristics={
                "volatility": "lower" if name == "Conservative" else "moderate",
                "growth_potential": "moderate" if name == "Conservative" else "higher",
            },
            risks=["Values can move up or down; returns are not guaranteed."],
            evidence=evidence[:2],
        )
