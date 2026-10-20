"""Unit tests for ticker symbol domain rules."""

import pytest

from app.domain.ticker import TickerSymbol


@pytest.mark.parametrize(
    ("raw_symbol", "expected"),
    [
        (" asml ", "ASML"),
        ("brk.b", "BRK.B"),
        ("btc-usd", "BTC-USD"),
        ("^gspc", "^GSPC"),
    ],
)
def test_ticker_symbol_normalizes_supported_symbols(raw_symbol, expected):
    assert TickerSymbol(raw_symbol).value == expected


@pytest.mark.parametrize(
    "raw_symbol",
    ["", " ", "A/B", "A" * 33, "DROP TABLE;"],
)
def test_ticker_symbol_rejects_unsafe_or_oversized_values(raw_symbol):
    with pytest.raises(ValueError):
        TickerSymbol(raw_symbol)
