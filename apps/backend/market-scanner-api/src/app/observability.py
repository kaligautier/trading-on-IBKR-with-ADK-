"""Structured log events that Cloud Logging can rank and attach to traces."""

import json
import logging
import os
import re

from app.utils.logging_messages import LoggingMessages

logger = logging.getLogger("market_scanner_api")
_TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})")


def trace_fields(traceparent: str | None) -> dict[str, str | bool]:
    """Correlation fields from a W3C ``traceparent``; this creates no span."""
    match = _TRACEPARENT.fullmatch(traceparent or "")
    if match is None or int(match[1], 16) == 0 or int(match[2], 16) == 0:
        return {}
    fields: dict[str, str | bool] = {"trace_id": match[1]}
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if project:
        fields.update(
            {
                "logging.googleapis.com/trace": f"projects/{project}/traces/{match[1]}",
                "logging.googleapis.com/spanId": match[2],
                "logging.googleapis.com/trace_sampled": bool(int(match[3], 16) & 1),
            }
        )
    return fields


def log_event(level: int, traceparent: str | None, fields: dict[str, object]) -> None:
    """Emit one JSON event with its severity and the caller's trace."""
    payload = {
        "severity": logging.getLevelName(level),
        **fields,
        **trace_fields(traceparent),
    }
    logger.log(level, LoggingMessages.STRUCTURED_EVENT, json.dumps(payload))
