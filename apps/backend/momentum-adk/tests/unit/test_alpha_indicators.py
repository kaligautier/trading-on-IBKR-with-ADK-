"""Keep vendor request parameters, dated CSV selection and report errors stable."""

from unittest.mock import Mock

import pytest

from app.infrastructure.market_data.alpha_vantage import indicator as adapter


@pytest.mark.parametrize(
    ("indicator", "function", "period", "column"),
    [
        ("close_50_sma", "SMA", "50", "SMA"),
        ("close_200_sma", "SMA", "200", "SMA"),
        ("close_10_ema", "EMA", "10", "EMA"),
        ("macd", "MACD", None, "MACD"),
        ("macds", "MACD", None, "MACD_Signal"),
        ("macdh", "MACD", None, "MACD_Hist"),
        ("rsi", "RSI", "7", "RSI"),
        ("boll", "BBANDS", "20", "Real Middle Band"),
        ("boll_ub", "BBANDS", "20", "Real Upper Band"),
        ("boll_lb", "BBANDS", "20", "Real Lower Band"),
        ("atr", "ATR", "7", "ATR"),
    ],
)
def test_indicator_requests_and_inclusive_sorted_window(
    monkeypatch, indicator, function, period, column
):
    request = Mock(
        return_value=(
            f"other,time,{column}\n"
            "0,2026-10-24,999\n0,2026-10-23,3\n0,2026-10-21,1\n"
            "malformed\n0,not-a-date,999\n0,2026-10-20,999\n\n"
        )
    )
    monkeypatch.setattr(adapter, "_make_api_request", request)
    result = adapter.get_indicator(
        "AAPL", indicator, "2026-10-23", 2, "weekly", 7, "open"
    )
    expected = {"symbol": "AAPL", "interval": "weekly", "datatype": "csv"}
    if period is not None:
        expected["time_period"] = period
    if indicator != "atr":
        expected["series_type"] = "close"
    request.assert_called_once_with(function, expected)
    assert result.startswith(
        f"## {indicator.upper()} values from 2026-10-21 to 2026-10-23:"
    )
    assert "2026-10-21: 1\n2026-10-23: 3\n" in result
    assert "999" not in result


@pytest.mark.parametrize(
    ("csv", "expected"),
    [
        ("", "Error: No data returned for rsi"),
        ("date,RSI\n2026-10-23,50", "Error: 'time' column not found"),
        ("time,wrong\n2026-10-23,50", "Error: Column 'RSI' not found"),
        ("time,RSI\n2026-10-20,50", "No data available for the specified date range."),
    ],
)
def test_empty_or_invalid_csv_preserves_report_errors(monkeypatch, csv, expected):
    monkeypatch.setattr(adapter, "_make_api_request", Mock(return_value=csv))
    assert expected in adapter.get_indicator("AAPL", "rsi", "2026-10-23", 2)


def test_vwma_and_invalid_arguments_do_not_call_provider(monkeypatch):
    request = Mock()
    monkeypatch.setattr(adapter, "_make_api_request", request)
    assert "not directly available" in adapter.get_indicator(
        "AAPL", "vwma", "2026-10-23", 2
    )
    with pytest.raises(ValueError, match="not supported"):
        adapter.get_indicator("AAPL", "unknown", "2026-10-23", 2)
    with pytest.raises(ValueError):
        adapter.get_indicator("AAPL", "rsi", "invalid-date", 2)
    request.assert_not_called()


def test_provider_failure_preserves_error_report(monkeypatch):
    monkeypatch.setattr(
        adapter, "_make_api_request", Mock(side_effect=RuntimeError("offline"))
    )
    assert (
        adapter.get_indicator("AAPL", "rsi", "2026-10-23", 2)
        == "Error retrieving rsi data: offline"
    )
