"""Logging configuration with JSON output and OpenTelemetry trace correlation."""

import logging

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter

from momentum_public_mcp.config.config import Settings
from momentum_public_mcp.config.constants import NOISY_LOGGERS


class TraceInjectFilter(logging.Filter):
    """Inject OpenTelemetry traceId and spanId into every log record."""

    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx and ctx.trace_id:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""

        return True


def config_logger(settings: Settings):
    """Configure JSON logging with trace correlation and the configured log level."""
    handler = logging.StreamHandler()
    handler.addFilter(TraceInjectFilter())

    fmt = (
        "%(levelname)s %(name)s %(module)s %(funcName)s"
        " %(message)s %(trace_id)s %(span_id)s"
    )
    formatter = JsonFormatter(
        fmt=fmt,
        rename_fields={"levelname": "severity"},
    )
    handler.setFormatter(formatter)

    logging.basicConfig(
        level=settings.LOG_LEVEL,
        handlers=[handler],
        force=True,
    )

    for noisy_logger in NOISY_LOGGERS:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured: level={settings.LOG_LEVEL}, app={settings.K_SERVICE}"
    )
