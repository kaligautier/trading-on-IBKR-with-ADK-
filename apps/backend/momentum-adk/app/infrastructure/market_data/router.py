from yfinance.exceptions import YFRateLimitError

# Import from vendor-specific modules
from app.infrastructure.market_data.alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_cashflow as get_alpha_vantage_cashflow,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_fundamentals as get_alpha_vantage_fundamentals,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_global_news as get_alpha_vantage_global_news,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_income_statement as get_alpha_vantage_income_statement,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_indicator as get_alpha_vantage_indicator,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_insider_transactions as get_alpha_vantage_insider_transactions,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_news as get_alpha_vantage_news,
)
from app.infrastructure.market_data.alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
)
from app.infrastructure.market_data.alpha_vantage.common import (
    AlphaVantageRateLimitError,
)

# Configuration and routing logic
from app.infrastructure.market_data.configuration import MarketDataConfiguration
from app.infrastructure.market_data.yahoo.finance import (
    get_balance_sheet as get_yfinance_balance_sheet,
)
from app.infrastructure.market_data.yahoo.finance import (
    get_cashflow as get_yfinance_cashflow,
)
from app.infrastructure.market_data.yahoo.finance import (
    get_fundamentals as get_yfinance_fundamentals,
)
from app.infrastructure.market_data.yahoo.finance import (
    get_income_statement as get_yfinance_income_statement,
)
from app.infrastructure.market_data.yahoo.finance import (
    get_insider_transactions as get_yfinance_insider_transactions,
)
from app.infrastructure.market_data.yahoo.finance import (
    get_stock_stats_indicators_window,
    get_YFin_data_online,
)
from app.infrastructure.market_data.yahoo.news import (
    get_global_news_yfinance,
    get_news_yfinance,
)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": ["get_stock_data"],
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"],
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
        ],
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ],
    },
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}


class MarketDataRouter:
    """Route a market-data request through an ordered vendor fallback chain."""

    def __init__(self, configuration: MarketDataConfiguration) -> None:
        self._configuration = configuration

    def route(self, method: str, *args, **kwargs):
        implementations = self._implementations(method)
        category = self._category(method)
        vendor = self._configuration.vendor_for(category, method)
        for vendor_name in self._fallback_vendors(vendor, implementations):
            try:
                return implementations[vendor_name](*args, **kwargs)
            except (AlphaVantageRateLimitError, YFRateLimitError):
                continue
        raise RuntimeError(f"No available vendor for '{method}'")

    @staticmethod
    def _category(method: str) -> str:
        for category, information in TOOLS_CATEGORIES.items():
            if method in information["tools"]:
                return category
        raise ValueError(f"Method '{method}' not found in any category")

    @staticmethod
    def _implementations(method: str) -> dict:
        implementations = VENDOR_METHODS.get(method)
        if implementations is None:
            raise ValueError(f"Method '{method}' not supported")
        return implementations

    @staticmethod
    def _fallback_vendors(primary: str, implementations: dict) -> list[str]:
        configured = [vendor.strip() for vendor in primary.split(",")]
        available = [vendor for vendor in configured if vendor in implementations]
        remaining = [vendor for vendor in implementations if vendor not in available]
        return [*available, *remaining]


def route_to_vendor(method: str, *args, **kwargs):
    """ADK function-tool boundary backed by the typed vendor router."""
    configuration = MarketDataConfiguration.from_environment()
    return MarketDataRouter(configuration).route(method, *args, **kwargs)
