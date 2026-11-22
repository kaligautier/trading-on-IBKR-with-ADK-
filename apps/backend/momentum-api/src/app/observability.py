"""Structured, bounded operational metadata; never log raw exceptions or payloads."""

import json
import logging
import os
import re
from datetime import UTC, datetime

from app.utils.logging_messages import LoggingMessages

LOGGER = logging.getLogger("momentum_api")
type LogValue = str | int | float | bool | None


def log_event(level: int, event: str, **fields: LogValue) -> None:
    try:
        LOGGER.log(
            level,
            LoggingMessages.STRUCTURED_EVENT,
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "severity": logging.getLevelName(level),
                    "event": event,
                    **fields,
                },
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    except Exception:
        # A secondary reporting failure must not change the operation's outcome.
        return


def trace_fields(values: list[str]) -> dict[str, str | bool]:
    """Read W3C version-00 correlation only; this creates no span or identity.

    With ``GOOGLE_CLOUD_PROJECT`` set, Cloud Logging attaches the entry to the
    caller's trace instead of leaving ``trace_id`` as a plain field.
    """
    if len(values) != 1:
        return {}
    match = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})", values[0])
    if match is None or int(match[1], 16) == 0 or int(match[2], 16) == 0:
        return {}
    fields: dict[str, str | bool] = {"trace_id": match[1], "parent_span_id": match[2]}
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
