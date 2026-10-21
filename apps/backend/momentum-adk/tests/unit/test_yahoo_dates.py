"""Date windows and provider fallback, without remote market calls."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from app.infrastructure.market_data import router
from app.infrastructure.market_data.yahoo import finance, news


@pytest.mark.parametrize(
    "method",
    ["get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement"],
)
def test_historical_fundamentals_do_not_fetch_current_data(monkeypatch, method):
    ticker = Mock(side_effect=AssertionError("current snapshot must not be read"))
    monkeypatch.setattr(finance.yf, "Ticker", ticker)
    assert "Historical fundamentals unavailable" in getattr(finance, method)(
        "AAPL", curr_date="2000-01-01"
    )
    ticker.assert_not_called()


def test_stock_range_includes_end_date(monkeypatch):
    history = Mock(
        return_value=pd.DataFrame(
            {"Close": [10]}, index=pd.DatetimeIndex(["2026-10-20"])
        )
    )
    monkeypatch.setattr(
        finance.yf, "Ticker", lambda symbol: SimpleNamespace(history=history)
    )
    assert "2026-10-20" in finance.get_YFin_data_online(
        "AAPL", "2026-10-20", "2026-10-20"
    )
    assert history.call_args.kwargs == {"start": "2026-10-20", "end": "2026-10-21"}


def test_exhausted_yahoo_retries_try_alpha(monkeypatch):
    history = Mock(side_effect=YFRateLimitError())
    monkeypatch.setattr(
        finance.yf, "Ticker", lambda symbol: SimpleNamespace(history=history)
    )
    monkeypatch.setattr(
        "app.infrastructure.market_data.stockstats.time.sleep", lambda _: None
    )
    alpha = Mock(return_value="fallback data")
    monkeypatch.setitem(
        router.VENDOR_METHODS,
        "get_stock_data",
        {"yfinance": finance.get_YFin_data_online, "alpha_vantage": alpha},
    )
    config = Mock()
    config.vendor_for.return_value = "yfinance"
    assert (
        router.MarketDataRouter(config).route(
            "get_stock_data", "AAPL", "2026-10-20", "2026-10-20"
        )
        == "fallback data"
    )
    assert history.call_count == 4
    alpha.assert_called_once()


def article(title, time, nested):
    if nested:
        return {"content": {"title": title, "pubDate": time}}
    return {
        "title": title,
        "providerPublishTime": datetime.fromisoformat(time).timestamp()
        if time
        else None,
    }


@pytest.mark.parametrize("nested", [True, False])
def test_news_filters_both_bounds_before_limit(monkeypatch, nested):
    articles = [
        article("too old", "2026-10-18T23:59:00+00:00", nested),
        article("last minute", "2026-10-20T23:59:00+00:00", nested),
        article("future", "2026-10-21T00:00:00+00:00", nested),
        article("unknown", None, nested),
    ]
    monkeypatch.setattr(
        news.yf, "Ticker", lambda _: SimpleNamespace(get_news=lambda **kw: articles)
    )
    monkeypatch.setattr(news.yf, "Search", lambda **kw: SimpleNamespace(news=articles))
    outputs = [
        news.get_news_yfinance("AAPL", "2026-10-19", "2026-10-20"),
        news.get_global_news_yfinance("2026-10-20", look_back_days=1, limit=1),
    ]
    for output in outputs:
        assert "last minute" in output
        assert all(title not in output for title in ("too old", "future", "unknown"))
    assert news._extract_article_data(articles[1])["pub_date"].tzinfo == timezone.utc
