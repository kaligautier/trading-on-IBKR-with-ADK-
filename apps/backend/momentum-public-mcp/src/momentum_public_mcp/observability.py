"""Bounded, payload-free telemetry for HTTP, tools and private API calls."""

import json
import logging
import logging.config
import re
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from fastmcp.server.middleware import Middleware

from momentum_public_mcp.constants import PUBLIC_TOOL_NAMES

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
trace_id: ContextVar[str] = ContextVar("trace_id", default="")
span_id: ContextVar[str] = ContextVar("span_id", default="")
tool_name: ContextVar[str] = ContextVar("tool_name", default="none")
logger = logging.getLogger("momentum_public_mcp.telemetry")
TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-0[01]\Z")


class JsonFormatter(logging.Formatter):
    """Never serialize exception text, request arguments or third-party messages."""

    def __init__(self, project=""):
        super().__init__()
        self.project = project

    def format(self, record):
        fields = {
            "severity": record.levelname,
            "logger": record.name,
            "event": "runtime_log",
            **getattr(record, "event_fields", {}),
        }
        project = self.project
        if project and fields.get("trace_id"):
            fields["logging.googleapis.com/trace"] = (
                f"projects/{project}/traces/{fields['trace_id']}"
            )
            fields["logging.googleapis.com/spanId"] = fields.get("span_id", "")
        return json.dumps(fields, separators=(",", ":"), allow_nan=False)


def configure_logging(project=""):
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter, "project": project}},
            "handlers": {
                "json": {"class": "logging.StreamHandler", "formatter": "json"}
            },
            "root": {"handlers": ["json"], "level": "INFO"},
            "loggers": {
                name: {"handlers": [], "propagate": True, "level": "INFO"}
                for name in ("fastmcp", "uvicorn", "uvicorn.error", "uvicorn.access")
            },
        }
    )


def emit(event, started, *, outcome, **fields):
    logger.log(
        logging.INFO if outcome == "success" else logging.WARNING,
        event,
        extra={
            "event_fields": {
                "event": event,
                "correlation_id": correlation_id.get(),
                "trace_id": trace_id.get(),
                "span_id": span_id.get(),
                "tool": tool_name.get(),
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "outcome": outcome,
                **fields,
            }
        },
    )


def outbound_headers():
    if not trace_id.get():
        return {}
    return {
        "X-Request-ID": correlation_id.get(),
        "traceparent": f"00-{trace_id.get()}-{span_id.get()}-01",
    }


class RequestTelemetry:
    """Generate independent correlation IDs; preserve only validated trace context."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        parent = TRACEPARENT.fullmatch(
            headers.get(b"traceparent", b"").decode("ascii", "ignore")
        )
        trace = (
            parent[1]
            if parent and int(parent[1], 16) and int(parent[2], 16)
            else uuid4().hex
        )
        tokens = (
            correlation_id.set(str(uuid4())),
            trace_id.set(trace),
            span_id.set(uuid4().hex[:16]),
        )
        started, status = perf_counter(), 500

        async def response(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", correlation_id.get().encode()),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, response)
        finally:
            path = scope.get("path")
            emit(
                "http_request",
                started,
                outcome="success" if status < 400 else "error",
                route=path if path in {"/", "/health"} else "other",
                method=scope["method"]
                if scope["method"] in {"GET", "POST", "OPTIONS", "DELETE", "HEAD"}
                else "other",
                status=status,
            )
            for variable, token in zip(
                (correlation_id, trace_id, span_id), tokens, strict=True
            ):
                variable.reset(token)


class ToolTelemetry(Middleware):
    async def on_call_tool(self, context, call_next):
        name = context.message.name
        token = tool_name.set(name if name in PUBLIC_TOOL_NAMES else "unknown")
        started, outcome, error_type = perf_counter(), "error", None
        try:
            result = await call_next(context)
            outcome = "error" if result.is_error else "success"
            return result
        except BaseException as error:
            error_type = type(error).__name__
            raise
        finally:
            emit("tool_call", started, outcome=outcome, error_type=error_type)
            tool_name.reset(token)
