"""Native FastMCP message logging with payload-free error summaries."""

import logging

from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.logging import LoggingMiddleware


def _redact_arguments(value):
    """Copy JSON arguments while masking credentials and opaque cursors."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(
                sensitive in key.casefold().replace("-", "_")
                for sensitive in (
                    "token",
                    "secret",
                    "password",
                    "authorization",
                    "api_key",
                    "apikey",
                    "cookie",
                )
            )
            else _redact_arguments(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_arguments(item) for item in value]
    return value


class RequestLoggingMiddleware(LoggingMiddleware):
    """Log method, source, outcome and duration through native on_message hooks."""

    def __init__(self) -> None:
        super().__init__(
            logger=logging.getLogger(__name__),
            include_payloads=False,
        )

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        args = context.message.arguments or {}
        self.logger.info(
            "event=tool_call tool=%s argument_count=%d",
            tool_name,
            len(args),
            extra={"tool": tool_name, "arguments": _redact_arguments(args)},
        )
        result = await call_next(context)
        return result

    def _create_error_message(
        self,
        context: MiddlewareContext,
        start_time: float,
        error: Exception,
    ) -> dict[str, str | int | float]:
        # include_payloads=False does not suppress str(error) in FastMCP 4.1.3.
        # Validation exceptions can embed argument values: log only their class.
        message = super()._create_error_message(context, start_time, error)
        message["error"] = type(error).__name__
        return message
