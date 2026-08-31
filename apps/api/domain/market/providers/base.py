"""Market data provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.market.contracts import MarketIndexSnapshot, SectorConstituent


class MarketDataProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    def get_broad_market_indices(self) -> list[MarketIndexSnapshot]:
        ...

    @abstractmethod
    def get_sectoral_indices(self) -> list[MarketIndexSnapshot]:
        ...

    @abstractmethod
    def get_index(self, index_code: str) -> MarketIndexSnapshot:
        ...

    def get_sector_constituents(self, sector_index_code: str, sector_name: str) -> list[SectorConstituent]:
        """Optional: fetch constituents for security classification."""
        return []
