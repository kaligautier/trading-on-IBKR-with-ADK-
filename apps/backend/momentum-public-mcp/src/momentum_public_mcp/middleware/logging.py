"""Structured tool-call logging with bounded, redacted arguments."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from momentum_public_mcp.constants import PUBLIC_TOOL_NAMES

logger = logging.getLogger(__name__)
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
)
_MAX_DEPTH = 5
_MAX_FIELDS = 40
_MAX_ITEMS = 20
_MAX_STRING_LENGTH = 256


def redact_arguments(value: Any, *, _depth: int = 0) -> Any:
    """Bound logged JSON arguments and redact credential-like fields."""
    if _depth >= _MAX_DEPTH:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        entries = list(value.items())
        redacted = {
            key: "[REDACTED]"
            if any(
                part in key.casefold().replace("-", "_")
                for part in _SENSITIVE_KEY_PARTS
            )
            else redact_arguments(item, _depth=_depth + 1)
            for key, item in entries[:_MAX_FIELDS]
        }
        if len(entries) > _MAX_FIELDS:
            redacted["_truncated_fields"] = len(entries) - _MAX_FIELDS
        return redacted
    if isinstance(value, list):
        items = [
            redact_arguments(item, _depth=_depth + 1) for item in value[:_MAX_ITEMS]
        ]
        if len(value) > _MAX_ITEMS:
            items.append(f"[TRUNCATED {len(value) - _MAX_ITEMS} items]")
        return items
    if isinstance(value, str) and len(value) > _MAX_STRING_LENGTH:
        return value[:_MAX_STRING_LENGTH] + "…[TRUNCATED]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return f"[UNSUPPORTED {type(value).__name__}]"


class ToolCallLoggingMiddleware(Middleware):
    """Log tool name, redacted inputs, result status and duration only."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        arguments = redact_arguments(context.message.arguments or {})
        started = perf_counter()
        fields = {
            "event": "tool_call",
            "tool": tool_name if tool_name in PUBLIC_TOOL_NAMES else "unknown",
            "arguments": arguments,
        }
        try:
            result = await call_next(context)
        except Exception as error:
            fields.update(
                outcome="error",
                error_type=type(error).__name__,
            )
            raise
        else:
            fields["outcome"] = "error" if result.is_error else "success"
            return result
        finally:
            fields["duration_ms"] = round((perf_counter() - started) * 1000, 3)
            logger.info(
                "tool_call",
                extra={"event_fields": fields},
            )
