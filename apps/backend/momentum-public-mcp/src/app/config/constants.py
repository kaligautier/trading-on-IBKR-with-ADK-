"""Public MCP metadata, instruction names and execution limits."""

from mcp.types import ToolAnnotations

from app.api.momentum.config.constants import (
    MOMENTUM_ANALYSIS_API_VERSION,
)

NOISY_LOGGERS = ("httpx", "httpcore")

TOOL_TIMEOUT_SECONDS = 45
DEFAULT_LIST_PAGE_SIZE = 100
ANALYZE_TICKER_INSTRUCTION = "analyze_ticker"
MOMENTUM_NAMESPACE = "momentum"
MARKET_SCANNER_NAMESPACE = "market_scanner"

PUBLIC_TOOL_NAMES = frozenset(
    f"{MOMENTUM_NAMESPACE}_{name}"
    for name in {
        "list_analyses",
        "latest_analyses",
        "get_analysis",
        "get_recommendations",
        "suggest_ticker",
        "get_suggestion_status",
    }
)

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
MODERATED_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    # Momentum returns the existing suggestion for a symbol without updating it.
    idempotent_hint=True,
    open_world_hint=True,
)

CONSULTATION_TOOL_OPTIONS = {
    "annotations": READ_ONLY,
    "timeout": TOOL_TIMEOUT_SECONDS,
}

ANALYSIS_TOOL_OPTIONS = {
    **CONSULTATION_TOOL_OPTIONS,
    "version": MOMENTUM_ANALYSIS_API_VERSION,
}

SUGGESTION_TOOL_OPTIONS = {
    "annotations": MODERATED_WRITE,
    "timeout": TOOL_TIMEOUT_SECONDS,
}
