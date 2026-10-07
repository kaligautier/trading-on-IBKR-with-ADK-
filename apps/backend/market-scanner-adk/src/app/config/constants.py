"""Application constants."""

from app.instructions.instructions_manager import InstructionsManager
from app.models.calendar_horizon import CalendarHorizon
from app.models.market_report import ASSET_FAMILIES

instruction_manager = InstructionsManager()

DEFAULT = "default"
SUCCESS = "success"

STABLE_TREND = "stable"
RISING_TREND = "rising"
FALLING_TREND = "falling"

YTD_HORIZON_LABEL = "ytd"
PERCENTILE_HORIZON = CalendarHorizon("3y", years=3)
MIN_PERCENTILE_OBSERVATIONS = 252
PRICE_DECIMAL_PLACES = 4
CHANGE_DECIMAL_PLACES = 2
DECIMAL_REFERENCE_MAX_WEEKDAYS = 5

MARKET_SCANNER = "market_scanner"
GET_MARKET_DATA = "get_market_data"
ENRICH_MARKET_DATA = "enrich_market_data"
ASSEMBLE_MARKET_DATA = "assemble_market_data"
PERSIST_MARKET_SCAN = "persist_market_scan"

MARKET_WEB_RESEARCHER_NAME = "market_web_researcher"
MARKET_RESEARCH_CRITIC_NAME = "market_research_critic"
MARKET_SYNTHESIZER_NAME = "market_synthesizer"
MARKET_SCANNER_AGENT_MODE = "single_turn"

ASSET_WEB_RESEARCHER_INSTRUCTION = instruction_manager.get_instructions(
    "market_scanner/asset_web_researcher_instruction", families=ASSET_FAMILIES
)

MARKET_RESEARCH_CRITIC_INSTRUCTION = instruction_manager.get_instructions(
    "market_scanner/market_research_critic_instruction", families=ASSET_FAMILIES
)

MARKET_SYNTHESIZER_INSTRUCTION = instruction_manager.get_instructions(
    "market_scanner/market_synthesizer_instruction", families=ASSET_FAMILIES
)

STATE_TRADING_CONFIG = "trading_config"
STATE_TREND_MARKET_DATA = "trend_market_data"
STATE_SESSION_ID = "session_id"
STATE_WEB_ANALYSIS = "web_analysis"
STATE_RESEARCH_CRITIQUE = "research_critique"
STATE_RESEARCH_SOURCES = "research_sources"
STATE_RESEARCH_CLAIMS = "research_claims"
STATE_RESEARCH_CAPTURE_COUNT = "research_capture_count"
STATE_RESEARCH_EVIDENCE_AUDIT = "research_evidence_audit"
STATE_MARKET_ANALYSIS = "market_analysis"
STATE_ANALYSED_MARKET_DATA = "analysed_market_data"
STATE_MARKET_DATA = "market_data"
STATE_PORTFOLIO_DATA = "portfolio_data"
STATE_LIVE_ORDERS_BEFORE_ORDER_EXECUTION_DATA = (
    "live_orders_before_order_execution_data"
)
STATE_USER_PROFILE = "user_profile"
STATE_PORTFOLIO_ANALYSIS = "portfolio_analysis"
STATE_STOCK_RESEARCH = "stock_research"
STATE_RESOLVED_CONIDS = "resolved_conids_this_run"
STATE_STOCK_PICK = "stock_pick"
STATE_ORDER_PLACER_REPORT = "order_placer_report"
STATE_ORDER_EXECUTION = "order_execution"
STATE_RUN_SYNTHESIS = "run_synthesis"
STATE_ACCOUNT_ID = "account_id"
STATE_PLACED_ORDER_KEYS = "placed_order_keys_this_run"
STATE_CURRENT_TRADE_INDEX = "current_trade_index"
STATE_CURRENT_TRADE = "current_trade"
STATE_CURRENT_TRADE_REPORT = "current_trade_report"
STATE_CURRENT_TRADE_ATTEMPTS = "current_trade_placer_attempts"
APP_NAME = "deep_copy_workflow"

ASSET_ENTRIES = {
    "vix": ("^VIX", "VIX (CBOE Volatility Index)"),
    "vxn": ("^VXN", "VXN — Nasdaq-100 Volatility"),
    "vxd": ("^VXD", "VXD — Dow Jones Volatility"),
    "vixeq": ("^VIXEQ", "Cboe S&P 500 Constituent Volatility Index"),
    "dspx": ("^DSPX", "Cboe S&P 500 Dispersion Index"),
    "sp500": ("^GSPC", "S&P 500"),
    "nasdaq100": ("^NDX", "NASDAQ 100"),
    "msci_world": ("URTH", "MSCI World (ETF URTH)"),
    "cac40": ("^FCHI", "CAC 40"),
    "stoxx600": ("^STOXX", "STOXX Europe 600"),
    "ftse100": ("^FTSE", "FTSE 100"),
    "gold": ("GC=F", "Gold Futures"),
    "oil": ("CL=F", "WTI Crude Oil"),
    "natgas": ("NG=F", "Natural Gas"),
    "russell2000": ("^RUT", "Russell 2000"),
    "dow": ("^DJI", "Dow Jones Industrial Average"),
    "eurusd": ("EURUSD=X", "EUR/USD"),
    "nikkei225": ("^N225", "Nikkei 225"),
    "us_public_debt": ("US_PUBLIC_DEBT", "US federal debt"),
    "hang_seng": ("^HSI", "Hang Seng"),
    "usdjpy": ("JPY=X", "USD/JPY"),
    "bitcoin": ("BTC-USD", "Bitcoin"),
    "silver": ("SI=F", "Silver Futures"),
    "us10y": ("^TNX", "US 10Y Treasury Yield"),
    "dxy": ("DX-Y.NYB", "US Dollar Index"),
}

ASSET_SOURCE_OVERRIDES = {
    "us_public_debt": (
        "U.S. Treasury",
        "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/",
    ),
}


HORIZONS = (
    CalendarHorizon("1d", days=1),
    CalendarHorizon("1w", days=7),
    CalendarHorizon("1m", months=1),
    CalendarHorizon("3m", months=3),
    CalendarHorizon("6m", months=6),
    CalendarHorizon(YTD_HORIZON_LABEL, year_to_date=True),
    CalendarHorizon("1y", years=1),
    CalendarHorizon("5y", years=5),
)
