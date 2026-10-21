"""Current financial snapshots; historical publication dates are unavailable."""

import json

from app.infrastructure.market_data.dates import require_current_fundamentals

from .common import _make_api_request


def _snapshot(function: str, ticker: str, curr_date: str | None) -> str:
    try:
        require_current_fundamentals(curr_date)
    except ValueError as error:
        return str(error)
    result = _make_api_request(function, {"symbol": ticker})
    if curr_date:
        data = json.loads(result)
        for key in ("annualReports", "quarterlyReports"):
            if key in data:
                data[key] = [
                    r for r in data[key] if r.get("fiscalDateEnding", "") <= curr_date
                ]
        return json.dumps(data)
    return result


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Company overview, supported only for the current UTC date."""
    return _snapshot("OVERVIEW", ticker, curr_date)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None):
    return _snapshot("BALANCE_SHEET", ticker, curr_date)


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None):
    return _snapshot("CASH_FLOW", ticker, curr_date)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None):
    return _snapshot("INCOME_STATEMENT", ticker, curr_date)
