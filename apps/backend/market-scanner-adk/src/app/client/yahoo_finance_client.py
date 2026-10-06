"""Yahoo Finance implementation of the market data client contract."""

from collections.abc import Callable
from typing import Any

import yfinance as yf
from curl_cffi.requests.exceptions import ConnectionError, Timeout
from yfinance.exceptions import YFRateLimitError

from app.client.market_data_client import MarketDataClient
from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)


class YahooFinanceClient(MarketDataClient):
    """Fetch and normalize closing prices from Yahoo Finance."""

    source_name = "Yahoo Finance"

    def __init__(self, ticker_factory: Callable[[str], Any] | None = None) -> None:
        self._ticker_factory = ticker_factory or yf.Ticker

    def fetch_closing_prices(self, symbol: str, period: str) -> ClosingPriceHistory:
        ticker = self._ticker_factory(symbol)
        for attempt in range(2):
            try:
                # Propagate failures instead of mistaking a timeout for no history.
                history = ticker.history(
                    period=period,
                    interval="1d",
                    auto_adjust=False,
                    back_adjust=False,
                    repair=False,
                    rounding=False,
                    timeout=15,
                    raise_errors=True,
                )
                break
            except (ConnectionError, Timeout, YFRateLimitError):
                if attempt == 1:
                    raise
        if history.empty:
            return ClosingPriceHistory(())
        prices = tuple(
            ClosingPrice(timestamp.date(), float(value))
            for timestamp, value in history["Close"].dropna().items()
        )
        return ClosingPriceHistory(prices)
