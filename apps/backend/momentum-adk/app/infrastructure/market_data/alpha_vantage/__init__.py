"""Stable Alpha Vantage facade backed by specialized dataflow modules."""

from app.infrastructure.market_data.alpha_vantage.fundamentals import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
)
from app.infrastructure.market_data.alpha_vantage.indicator import get_indicator
from app.infrastructure.market_data.alpha_vantage.news import (
    get_global_news,
    get_insider_transactions,
    get_news,
)
from app.infrastructure.market_data.alpha_vantage.stock import get_stock

__all__ = [
    "get_balance_sheet",
    "get_cashflow",
    "get_fundamentals",
    "get_global_news",
    "get_income_statement",
    "get_indicator",
    "get_insider_transactions",
    "get_news",
    "get_stock",
]
