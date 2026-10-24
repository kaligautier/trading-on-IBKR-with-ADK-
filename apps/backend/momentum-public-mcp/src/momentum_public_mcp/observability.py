"""One bounded canonical event per request, enriched before tail sampling."""

import json
import logging
import logging.config
import random
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastmcp.server.middleware import Middleware

from momentum_public_mcp.constants import PUBLIC_TOOL_NAMES
from momentum_public_mcp.domain import (
    AnalysisDetail,
    AnalysisSummaries,
    MarketScan,
    Suggestion,
)

request_event: ContextVar[dict | None] = ContextVar("request_event", default=None)
logger = logging.getLogger("momentum_public_mcp.telemetry")
TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-0[01]\Z")


class JsonFormatter(logging.Formatter):
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
        if self.project and fields.get("trace_id"):
            fields["logging.googleapis.com/trace"] = (
                f"projects/{self.project}/traces/{fields['trace_id']}"
            )
            fields["logging.googleapis.com/spanId"] = fields["span_id"]
        return json.dumps(fields, separators=(",", ":"), allow_nan=False)


class CanonicalRequestFilter(logging.Filter):
    """Suppress per-request library chatter; the final event records its outcome."""

    def filter(self, record):
        return request_event.get() is None or hasattr(record, "event_fields")


def configure_logging(project=""):
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter, "project": project}},
            "filters": {"canonical": {"()": CanonicalRequestFilter}},
            "handlers": {
                "json": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["canonical"],
                }
            },
            "root": {"handlers": ["json"], "level": "INFO"},
            "loggers": {
                name: {"handlers": [], "propagate": True, "level": "INFO"}
                for name in ("fastmcp", "uvicorn", "uvicorn.error", "uvicorn.access")
            },
        }
    )


def elapsed(started):
    return round((perf_counter() - started) * 1000, 3)


def record_upstream(upstream, started, *, status, outcome, error_type):
    event = request_event.get()
    if event is None:
        return
    name = upstream if upstream in {"momentum", "scanner"} else "other"
    summary = event["upstreams"].setdefault(
        name, {"calls": 0, "errors": 0, "duration_ms": 0}
    )
    summary["calls"] += 1
    summary["errors"] += int(outcome == "error")
    summary["duration_ms"] = round(summary["duration_ms"] + elapsed(started), 3)
    summary.update(last_status=status, last_error_type=error_type)


def record_result(result):
    """Attach useful business outcomes without storing inputs or response payloads."""
    event = request_event.get()
    if event is None:
        return
    if isinstance(result, AnalysisSummaries):
        event["business"] = {"result_count": len(result.items)}
    elif isinstance(result, AnalysisDetail):
        event["business"] = {"record_found": True}
    elif isinstance(result, MarketScan):
        assets = result.report.get("assets")
        event["business"] = {
            "asset_count": len(assets) if isinstance(assets, list) else None
        }
    elif isinstance(result, Suggestion):
        status = (
            result.status
            if result.status in {"pending", "approved", "rejected"}
            else "other"
        )
        event["business"] = {"suggestion_status": status}


def outbound_headers():
    event = request_event.get()
    if event is None:
        return {}
    return {
        "X-Request-ID": event["correlation_id"],
        "traceparent": f"00-{event['trace_id']}-{event['span_id']}-01",
    }


class RequestTelemetry:
    def __init__(
        self,
        app,
        *,
        success_sample_rate=1.0,
        slow_request_ms=2000,
        service="momentum-public-mcp",
        revision="local",
    ):
        self.app = app
        self.success_sample_rate = success_sample_rate
        self.slow_request_ms = slow_request_ms
        self.service, self.revision = service, revision

    def _event(self, scope):
        headers = dict(scope.get("headers", []))
        parent = TRACEPARENT.fullmatch(
            headers.get(b"traceparent", b"").decode("ascii", "ignore")
        )
        trace = (
            parent[1]
            if parent and int(parent[1], 16) and int(parent[2], 16)
            else uuid4().hex
        )
        path, method = scope.get("path"), scope["method"]
        return {
            "event": "request_completed",
            "schema_version": 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": str(uuid4()),
            "trace_id": trace,
            "span_id": uuid4().hex[:16],
            "service": self.service,
            "revision": self.revision,
            "http": {
                "route": path if path in {"/", "/health"} else "other",
                "method": method
                if method in {"GET", "POST", "OPTIONS", "DELETE", "HEAD"}
                else "other",
                "status": 500,
            },
            "upstreams": {},
        }

    def _finish(self, event, started):
        event["duration_ms"] = elapsed(started)
        failed = (
            event["http"]["status"] >= 400
            or "error_type" in event
            or event.get("tool", {}).get("outcome") == "error"
        )
        event["outcome"] = "error" if failed else "success"
        keep = failed or event["duration_ms"] >= self.slow_request_ms
        if keep or random.random() < self.success_sample_rate:
            event["sample_rate"] = 1.0 if keep else self.success_sample_rate
            logger.log(
                logging.WARNING if failed else logging.INFO,
                "request_completed",
                extra={"event_fields": event},
            )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        event = self._event(scope)
        token, started = request_event.set(event), perf_counter()

        async def response(message):
            if message["type"] == "http.response.start":
                event["http"]["status"] = message["status"]
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", event["correlation_id"].encode()),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, response)
        except BaseException as error:
            event["error_type"] = type(error).__name__
            raise
        finally:
            try:
                self._finish(event, started)
            finally:
                request_event.reset(token)


class ToolTelemetry(Middleware):
    async def on_call_tool(self, context, call_next):
        event = request_event.get()
        name = context.message.name
        tool = {
            "name": name if name in PUBLIC_TOOL_NAMES else "unknown",
            "outcome": "error",
        }
        if event is not None:
            event["tool"] = tool
        started = perf_counter()
        try:
            result = await call_next(context)
            tool["outcome"] = "error" if result.is_error else "success"
            return result
        except BaseException as error:
            tool["error_type"] = type(error).__name__
            raise
        finally:
            tool["duration_ms"] = elapsed(started)
