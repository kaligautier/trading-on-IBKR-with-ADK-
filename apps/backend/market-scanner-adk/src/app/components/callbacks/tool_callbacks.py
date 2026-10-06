"""Tool callbacks enriching the request wide event with safe identifiers."""

from typing import Any

from google.adk.tools import BaseTool, ToolContext

from app.utils.wide_event import wide_event


def record_tool_start(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict | None:
    """Record only the tool name; arguments may contain sensitive data."""
    wide_event.append("tools.called", tool.name)
    return None


def record_tool_end(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> dict | None:
    """Record completion without copying the potentially sensitive response."""
    wide_event.append("tools.completed", tool.name)
    return None
