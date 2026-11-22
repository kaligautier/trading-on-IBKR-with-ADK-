"""Log message templates shared by the whole application.

Each constant is a ``%s`` template or a fixed message. Pass it to the logger with
its arguments, ``logger.info(LoggingMessages.TOOL_CALL, extra=...)``, so the
message is only formatted when the record is actually emitted. Structured fields
stay in ``extra["event_fields"]``; ruff rule G004 rejects f-strings in logging
calls.
"""


class LoggingMessages:
    """Reusable log messages, grouped by the area that emits them."""

    # HTTP requests (one canonical event per request)
    REQUEST_COMPLETED = "request_completed"

    # MCP tools
    TOOL_CALL = "tool_call"
