"""Regression checks for Alpha Vantage calendar bounds and historical safety."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd
import pytest

from app.infrastructure.market_data import stockstats
from app.infrastructure.market_data.alpha_vantage import fundamentals, news


@pytest.mark.parametrize(
    "method",
    ["get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement"],
)
def test_historical_snapshot_is_unavailable_without_network(monkeypatch, method):
    request = Mock(side_effect=AssertionError("must not fetch today's snapshot"))
    monkeypatch.setattr(fundamentals, "_make_api_request", request)
    assert "Historical fundamentals unavailable" in getattr(fundamentals, method)(
        "AAPL", curr_date="2000-01-01"
    )
    request.assert_not_called()


def test_statement_decodes_text_before_filtering_future_periods(monkeypatch):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    monkeypatch.setattr(
        fundamentals,
        "_make_api_request",
        Mock(
            return_value='{"annualReports":[{"fiscalDateEnding":"2000-01-01"},{"fiscalDateEnding":"9999-01-01"}]}'
        ),
    )
    result = fundamentals.get_balance_sheet("AAPL", curr_date=today)
    assert "2000-01-01" in result and "9999-01-01" not in result


@pytest.mark.parametrize(
    "end,expected",
    [("2026-10-20", "20261020T2359"), ("2026-10-20 12:30", "20261020T1230")],
)
def test_news_date_includes_end_day_and_preserves_timestamps(
    monkeypatch, end, expected
):
    request = Mock(return_value="{}")
    monkeypatch.setattr(news, "_make_api_request", request)
    news.get_news("AAPL", "2026-10-20", end)
    assert request.call_args.args[1]["time_to"] == expected
    news.get_global_news("2026-10-20")
    assert request.call_args.args[1]["time_to"] == "20261020T2359"


def test_prices_keep_fifteen_year_window_for_older_analysis(monkeypatch, tmp_path):
    monkeypatch.setenv("MOMENTUM_CACHE_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(
        stockstats.MarketDataConfiguration,
        "from_environment",
        lambda: Mock(cache_directory=tmp_path),
    )
    old = pd.Timestamp.today().normalize() - pd.DateOffset(years=8)
    frame = pd.DataFrame(
        {"Close": [100, 200]},
        index=pd.DatetimeIndex([old, pd.Timestamp.today().normalize()], name="Date"),
    )
    download = Mock(return_value=frame)
    monkeypatch.setattr(stockstats.yf, "download", download)
    result = stockstats.load_ohlcv("EURUSD=X", old.strftime("%Y-%m-%d"))
    assert list(result["Close"]) == [100]
    assert pd.Timestamp(download.call_args.kwargs["start"]) <= old - pd.DateOffset(
        years=6
    )
