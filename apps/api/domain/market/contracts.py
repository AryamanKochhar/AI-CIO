"""Normalized market intelligence contracts. NSE raw JSON must not leak past providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class MarketIndexSnapshot:
    provider: str
    index_code: str
    index_name: str
    category: str  # broad | sector
    timestamp: datetime
    current_value: Decimal | None
    previous_close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    day_high: Decimal | None
    day_low: Decimal | None
    year_high: Decimal | None
    year_low: Decimal | None
    source: str
    is_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        def _m(v: Decimal | None) -> str | None:
            return f"{v:.4f}" if v is not None else None

        return {
            "provider": self.provider,
            "index_code": self.index_code,
            "index_name": self.index_name,
            "category": self.category,
            "timestamp": self.timestamp.isoformat(),
            "current_value": _m(self.current_value),
            "previous_close": _m(self.previous_close),
            "change": _m(self.change),
            "change_percent": _m(self.change_percent),
            "day_high": _m(self.day_high),
            "day_low": _m(self.day_low),
            "year_high": _m(self.year_high),
            "year_low": _m(self.year_low),
            "source": self.source,
            "is_stale": self.is_stale,
        }


@dataclass(frozen=True)
class SectorConstituent:
    symbol: str
    name: str
    isin: str | None
    sector_index_code: str
    sector_name: str


@dataclass
class MarketAnalytics:
    as_of: datetime
    benchmark_code: str
    benchmark_change_percent: Decimal | None
    sectors: list[dict[str, Any]] = field(default_factory=list)
    breadth: dict[str, Any] = field(default_factory=dict)
    is_stale: bool = False
    source: str = "nse"


@dataclass
class SectorExposure:
    sector_index_code: str
    sector_name: str
    value: Decimal
    weight_percent: Decimal | None
    exposure_type: str  # direct | indirect | unknown
    holdings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OpportunityCandidate:
    type: str
    sector_index_code: str | None
    sector_name: str | None
    market_move_percent: Decimal | None
    benchmark_move_percent: Decimal | None
    relative_move_percent: Decimal | None
    user_exposure_percent: Decimal | None
    user_exposure_value: Decimal | None
    reason_codes: list[str]
    severity: str
    index_code: str | None = None


@dataclass
class TwinAnalysisContext:
    portfolio: dict[str, Any]
    goals: list[dict[str, Any]]
    behavioural: dict[str, Any]
    completeness: dict[str, bool]
    twin_as_of: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio": self.portfolio,
            "goals": self.goals,
            "behavioural": self.behavioural,
            "completeness": self.completeness,
            "twin_as_of": self.twin_as_of.isoformat() if self.twin_as_of else None,
        }


@dataclass
class MarketOpportunityAnalysis:
    opportunity_type: str
    summary: str
    why_relevant: list[str]
    market_facts: list[str]
    portfolio_facts: list[str]
    risks: list[str]
    missing_information: list[str]
    knowledge_references: list[dict[str, str]]
    confidence: str
    recommended_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_type": self.opportunity_type,
            "summary": self.summary,
            "why_relevant": self.why_relevant,
            "market_facts": self.market_facts,
            "portfolio_facts": self.portfolio_facts,
            "risks": self.risks,
            "missing_information": self.missing_information,
            "knowledge_references": self.knowledge_references,
            "confidence": self.confidence,
            "recommended_next_step": self.recommended_next_step,
        }
