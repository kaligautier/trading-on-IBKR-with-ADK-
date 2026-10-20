"""Thin ADK-compatible tools over the existing market-data boundary."""

import os
from typing import Annotated

import requests

from app.infrastructure.market_data.router import route_to_vendor


def get_stock_data(
    symbol: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
) -> str:
    """Retrieve OHLCV stock prices for an instrument and date range."""
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


def get_indicators(
    symbol: Annotated[str, "Ticker symbol"],
    indicator: Annotated[str, "One or more comma-separated indicator names"],
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
    look_back_days: Annotated[int, "Number of calendar days to inspect"],
) -> str:
    """Retrieve technical indicators for an instrument."""
    indicators = [item.strip().lower() for item in indicator.split(",")]
    reports = [
        _indicator_report(symbol, name, curr_date, look_back_days)
        for name in indicators
        if name
    ]
    return "\n\n".join(reports)


def _indicator_report(
    symbol: str,
    indicator: str,
    current_date: str,
    look_back_days: int,
) -> str:
    try:
        return route_to_vendor(
            "get_indicators", symbol, indicator, current_date, look_back_days
        )
    except ValueError as error:
        return str(error)


def get_fundamentals(
    ticker: Annotated[str, "Ticker symbol"],
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve comprehensive fundamental data for an instrument."""
    return route_to_vendor("get_fundamentals", ticker, curr_date)


def get_balance_sheet(
    ticker: Annotated[str, "Ticker symbol"],
    freq: Annotated[str, "Reporting frequency: annual or quarterly"],
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve an instrument's balance sheet."""
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


def get_cashflow(
    ticker: Annotated[str, "Ticker symbol"],
    freq: Annotated[str, "Reporting frequency: annual or quarterly"],
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve an instrument's cash-flow statement."""
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


def get_income_statement(
    ticker: Annotated[str, "Ticker symbol"],
    freq: Annotated[str, "Reporting frequency: annual or quarterly"],
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve an instrument's income statement."""
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
) -> str:
    """Retrieve instrument-specific news and sentiment sources."""
    return route_to_vendor("get_news", ticker, start_date, end_date)


def get_global_news(
    curr_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
    look_back_days: Annotated[int, "Number of days to inspect"],
    limit: Annotated[int, "Maximum number of articles"],
) -> str:
    """Retrieve global macroeconomic news."""
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)


def get_insider_transactions(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """Retrieve insider transactions for an instrument."""
    return route_to_vendor("get_insider_transactions", ticker)


def get_latest_market_scan() -> str:
    """Retrieve the latest persisted daily market scan from its API."""
    base_url = os.environ.get("TA_MARKET_SCANNER_API_URL", "").rstrip("/")
    if not base_url:
        return "Market scanner API is not configured."
    try:
        response = requests.get(f"{base_url}/market-scans/latest", timeout=12)
        response.raise_for_status()
        return response.text
    except requests.RequestException as error:
        return f"Market scanner API unavailable: {error}"
