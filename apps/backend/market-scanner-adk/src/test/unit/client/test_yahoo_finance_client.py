"""Tests for the Yahoo Finance market data client."""

from datetime import date, datetime
from unittest.mock import Mock

import pytest
from curl_cffi.requests.exceptions import Timeout
from yfinance.exceptions import YFRateLimitError

from app.client.yahoo_finance_client import YahooFinanceClient
from app.dto.external.response.market_data_response_dto import ClosingPrice


class FakePriceSeries:
    def dropna(self):
        return self

    def items(self):
        return [
            (datetime(2026, 8, 13, 0, 0), 100.0),
            (datetime(2026, 8, 14, 0, 0), 101.5),
        ]


class FakeHistory:
    empty = False

    def __getitem__(self, column: str):
        if column != "Close":
            raise KeyError(column)
        return FakePriceSeries()


class EmptyHistory:
    empty = True


class FakeTicker:
    def __init__(self, history) -> None:
        self._history = history
        self.requested_period: str | None = None

    def history(self, *, period: str, timeout: int, raise_errors: bool, **options):
        assert timeout == 15
        assert raise_errors is True
        assert options == {
            "interval": "1d",
            "auto_adjust": False,
            "back_adjust": False,
            "repair": False,
            "rounding": False,
        }
        self.requested_period = period
        return self._history


class FakeTickerFactory:
    def __init__(self, ticker: FakeTicker) -> None:
        self._ticker = ticker
        self.requested_symbol: str | None = None

    def __call__(self, symbol: str) -> FakeTicker:
        self.requested_symbol = symbol
        return self._ticker


def should_return_provider_independent_closing_prices():
    ticker = FakeTicker(FakeHistory())
    ticker_factory = FakeTickerFactory(ticker)

    result = YahooFinanceClient(ticker_factory).fetch_closing_prices("^GSPC", "5y")

    assert result.prices == (
        ClosingPrice(date(2026, 8, 13), 100.0),
        ClosingPrice(date(2026, 8, 14), 101.5),
    )
    assert ticker_factory.requested_symbol == "^GSPC"
    assert ticker.requested_period == "5y"


def should_return_an_empty_collection_when_history_is_empty():
    ticker = FakeTicker(EmptyHistory())

    result = YahooFinanceClient(FakeTickerFactory(ticker)).fetch_closing_prices(
        "^GSPC", "5y"
    )

    assert result.prices == ()


@pytest.mark.parametrize("error", [Timeout("timeout"), YFRateLimitError()])
def should_retry_a_temporary_yahoo_failure_once(error):
    ticker = Mock()
    ticker.history.side_effect = [error, FakeHistory()]

    result = YahooFinanceClient(lambda _: ticker).fetch_closing_prices("^VXN", "5y")

    assert len(result.prices) == 2
    assert ticker.history.call_count == 2


def should_stop_after_two_temporary_failures():
    ticker = Mock()
    ticker.history.side_effect = Timeout("timeout")
    with pytest.raises(Timeout):
        YahooFinanceClient(lambda _: ticker).fetch_closing_prices("^VXD", "5y")
    assert ticker.history.call_count == 2


def should_not_retry_invalid_provider_data():
    ticker = Mock()
    ticker.history.side_effect = ValueError("invalid history")
    with pytest.raises(ValueError):
        YahooFinanceClient(lambda _: ticker).fetch_closing_prices("^VXN", "5y")
    assert ticker.history.call_count == 1
