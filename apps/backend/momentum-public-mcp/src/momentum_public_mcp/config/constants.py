"""Public MCP tool metadata and execution limits."""

from mcp.types import ToolAnnotations

TOOL_TIMEOUT_SECONDS = 45
DEFAULT_LIST_PAGE_SIZE = 100
MOMENTUM_API_VERSION = "0.1.0"
MARKET_SCANNER_API_VERSION = "1.0.0"
MOMENTUM_API_PREFIX = "/v1"
MARKET_SCANNER_API_PREFIX = "/v1"
MOMENTUM_NAMESPACE = "momentum"
MARKET_SCANNER_NAMESPACE = "market_scanner"

PUBLIC_TOOL_NAMES = {
    f"{MOMENTUM_NAMESPACE}_list_analyses",
    f"{MOMENTUM_NAMESPACE}_latest_analyses",
    f"{MOMENTUM_NAMESPACE}_get_analysis",
    f"{MOMENTUM_NAMESPACE}_get_recommendations",
    f"{MOMENTUM_NAMESPACE}_suggest_ticker",
    f"{MOMENTUM_NAMESPACE}_get_suggestion_status",
}

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
MODERATED_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

CONSULTATION_TOOL_OPTIONS = {
    "tags": {"public", "consultation"},
    "annotations": READ_ONLY,
    "timeout": TOOL_TIMEOUT_SECONDS,
    "version": MOMENTUM_API_VERSION,
}

LIST_ANALYSES_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "name": "list_analyses",
    "title": "List analyses",
    "description": (
        "Read one page of saved Momentum analysis history. Continue with the "
        "returned next_page_token and the same ticker filter."
    ),
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "GET",
            "path": f"{MOMENTUM_API_PREFIX}/analyses",
        }
    },
}
LATEST_ANALYSES_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "name": "latest_analyses",
    "title": "Latest analyses",
    "description": (
        "Read one page of the latest saved analysis for each ticker. Continue "
        "with the returned next_page_token and the same filters."
    ),
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "GET",
            "path": f"{MOMENTUM_API_PREFIX}/analyses/latest",
        }
    },
}
GET_ANALYSIS_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "name": "get_analysis",
    "title": "Get analysis",
    "description": "Read a complete saved Momentum analysis by UUID.",
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "GET",
            "path": f"{MOMENTUM_API_PREFIX}/analyses/{{analysis_id}}",
        }
    },
}
GET_RECOMMENDATIONS_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "name": "get_recommendations",
    "title": "Get recommendations",
    "description": (
        "Read one page of saved recommendations matching portfolio ratings. "
        "Continue with the returned next_page_token and the same rating filter."
    ),
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "GET",
            "path": f"{MOMENTUM_API_PREFIX}/recommendations",
        }
    },
}
SUGGEST_TICKER_TOOL = {
    "name": "suggest_ticker",
    "title": "Suggest ticker",
    "tags": {"public", "suggestion"},
    "description": (
        "Submit a ticker and optional reason for administrator review. A new "
        "suggestion remains pending and never starts an analysis."
    ),
    "annotations": MODERATED_WRITE,
    "timeout": TOOL_TIMEOUT_SECONDS,
    "version": MOMENTUM_API_VERSION,
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "POST",
            "path": f"{MOMENTUM_API_PREFIX}/suggestions",
        }
    },
}
GET_SUGGESTION_STATUS_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "name": "get_suggestion_status",
    "title": "Get suggestion status",
    "description": "Read the current moderation status for a suggestion UUID.",
    "meta": {
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
            "method": "GET",
            "path": f"{MOMENTUM_API_PREFIX}/suggestions/{{suggestion_id}}",
        }
    },
}
