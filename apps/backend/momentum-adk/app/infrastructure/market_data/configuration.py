"""Typed configuration for market-data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config.storage import MomentumStorage


@dataclass(frozen=True, slots=True)
class MarketDataConfiguration:
    """Select vendors and the local cache used by their adapters."""

    cache_directory: Path
    category_vendors: dict[str, str] = field(default_factory=dict)
    tool_vendors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> MarketDataConfiguration:
        storage = MomentumStorage.from_environment()
        return cls(
            cache_directory=storage.cache_directory,
            category_vendors={
                "core_stock_apis": "yfinance",
                "technical_indicators": "yfinance",
                "fundamental_data": "yfinance",
                "news_data": "yfinance",
            },
        )

    def vendor_for(self, category: str, method: str) -> str:
        tool_vendor = self.tool_vendors.get(method)
        if tool_vendor:
            return tool_vendor
        return self.category_vendors.get(category, "default")
