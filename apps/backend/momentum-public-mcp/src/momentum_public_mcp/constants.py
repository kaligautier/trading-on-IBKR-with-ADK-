"""Public MCP tool metadata and execution limits."""

from mcp.types import ToolAnnotations

TOOL_TIMEOUT_SECONDS = 45

PUBLIC_TOOL_NAMES = {
    "list_analyses",
    "latest_analyses",
    "get_analysis",
    "get_recommendations",
    "latest_market_scan",
    "suggest_ticker",
    "get_suggestion_status",
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
}

LIST_ANALYSES_TOOL = {**CONSULTATION_TOOL_OPTIONS, "title": "List analyses"}
LATEST_ANALYSES_TOOL = {**CONSULTATION_TOOL_OPTIONS, "title": "Latest analyses"}
GET_ANALYSIS_TOOL = {**CONSULTATION_TOOL_OPTIONS, "title": "Get analysis"}
GET_RECOMMENDATIONS_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "title": "Get recommendations",
}
LATEST_MARKET_SCAN_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "title": "Latest market scan",
    "tags": {"public", "market"},
}
SUGGEST_TICKER_TOOL = {
    "title": "Suggest ticker",
    "tags": {"public", "suggestion"},
    "annotations": MODERATED_WRITE,
    "timeout": TOOL_TIMEOUT_SECONDS,
}
GET_SUGGESTION_STATUS_TOOL = {
    **CONSULTATION_TOOL_OPTIONS,
    "title": "Get suggestion status",
}
