from .common import _make_api_request, format_datetime_for_api


def _end_time(value):
    # Preserve explicit timestamps; calendar dates include their final minute.
    if isinstance(value, str) and len(value) == 10:
        value += " 23:59"
    return format_datetime_for_api(value)


def get_news(ticker, start_date, end_date) -> dict[str, str] | str:
    """News for a ticker, including the whole end_date when it is a date."""

    params = {
        "tickers": ticker,
        "time_from": format_datetime_for_api(start_date),
        "time_to": _end_time(end_date),
    }

    return _make_api_request("NEWS_SENTIMENT", params)


def get_global_news(
    curr_date, look_back_days: int = 7, limit: int = 50
) -> dict[str, str] | str:
    """Global news through curr_date, with an explicit look-back and limit."""
    from datetime import datetime, timedelta

    # Calculate start date
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    params = {
        "topics": "financial_markets,economy_macro,economy_monetary",
        "time_from": format_datetime_for_api(start_date),
        "time_to": _end_time(curr_date),
        "limit": str(limit),
    }

    return _make_api_request("NEWS_SENTIMENT", params)


def get_insider_transactions(symbol: str) -> dict[str, str] | str:
    """Latest and historical insider transactions for symbol."""

    params = {
        "symbol": symbol,
    }

    return _make_api_request("INSIDER_TRANSACTIONS", params)
