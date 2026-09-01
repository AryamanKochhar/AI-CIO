"""Interfaces the orchestration layer depends on. Implementations live in services."""

from __future__ import annotations

from typing import Any, Protocol

from domain.decision.capabilities import Capability
from domain.decision.contracts import AnalysisResult, DecisionObjective, Evidence, InvestmentContext


class TwinDataProvider(Protocol):
    def load_twin(self, user_id: int) -> dict[str, Any]: ...


class MarketDataProvider(Protocol):
    def load_market_context(self, user_id: int) -> dict[str, Any]: ...


class KnowledgeProvider(Protocol):
    def resolve(self, *, objective: DecisionObjective, topics: list[str]) -> list[Evidence]: ...


class DecisionAnalyzer(Protocol):
    def analyze(
        self,
        context: InvestmentContext,
        *,
        capabilities: list[Capability],
    ) -> AnalysisResult: ...
