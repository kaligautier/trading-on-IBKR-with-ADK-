"""W3C trace context read from the request, used only to correlate logs."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})")


@dataclass(frozen=True)
class TraceContext:
    """Identifiers of the caller's span; this service creates no span itself."""

    trace_id: str
    span_id: str
    sampled: bool

    @classmethod
    def from_traceparent(cls, value: str | None) -> TraceContext | None:
        """Parse a version-00 ``traceparent``; ignore anything malformed."""
        match = _TRACEPARENT.fullmatch(value or "")
        if match is None or int(match[1], 16) == 0 or int(match[2], 16) == 0:
            return None
        return cls(
            trace_id=match[1],
            span_id=match[2],
            sampled=bool(int(match[3], 16) & 1),
        )

    def log_fields(self, project: str) -> dict[str, str | bool]:
        """Fields that let Cloud Logging attach the entry to its trace."""
        fields: dict[str, str | bool] = {"trace_id": self.trace_id}
        if project:
            fields.update(
                {
                    "logging.googleapis.com/trace": (
                        f"projects/{project}/traces/{self.trace_id}"
                    ),
                    "logging.googleapis.com/spanId": self.span_id,
                    "logging.googleapis.com/trace_sampled": self.sampled,
                }
            )
        return fields
