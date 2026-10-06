"""Provider-independent market data client contract."""

from abc import ABC, abstractmethod

from app.dto.external.response.market_data_response_dto import ClosingPriceHistory


class MarketDataClient(ABC):
    """Retrieve normalized market data from an external provider."""

    source_name: str | None = None

    @abstractmethod
    def fetch_closing_prices(self, symbol: str, period: str) -> ClosingPriceHistory:
        """Return chronological dated closing prices for a provider symbol."""
