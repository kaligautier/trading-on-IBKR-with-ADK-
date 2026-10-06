"""Unit tests for structured logging."""

import json
import logging

from app.utils.logger import JsonFormatter
from app.utils.wide_event import wide_event


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="market scan completed",
        args=(),
        exc_info=None,
    )


class TestJsonFormatter:
    def should_render_extra_fields_as_queryable_json(self):
        record = _record()
        record.__dict__["scan.asset_count"] = 12
        record.__dict__["outcome"] = "success"

        payload = json.loads(JsonFormatter().format(record))

        assert payload["message"] == "market scan completed"
        assert payload["level"] == "INFO"
        assert payload["scan.asset_count"] == 12
        assert payload["outcome"] == "success"

    def should_include_the_request_id_from_the_active_event(self):
        scope = wide_event.start({}, request_id="request-42")
        try:
            payload = json.loads(JsonFormatter().format(_record()))
        finally:
            wide_event.reset(scope)

        assert payload["request_id"] == "request-42"

    def should_serialize_unknown_extra_values_safely(self):
        record = _record()
        record.__dict__["value"] = object()

        payload = json.loads(JsonFormatter().format(record))

        assert isinstance(payload["value"], str)


def should_bound_oversized_json_logs_and_preserve_outcome_and_correlation():
    from app.utils.logger import MAX_LOG_BYTES

    record = _record()
    record.__dict__.update(
        {
            "request_id": "request-large",
            "event": "http.request",
            "persistence.status": "error",
            "http.status": 200,
            "error.kind": "RuntimeError",
            "unexpected_payload": "é" * 1000000,
        }
    )
    encoded = JsonFormatter().format(record)
    payload = json.loads(encoded)
    assert len(encoded.encode()) < MAX_LOG_BYTES
    assert payload["log.truncated"] is True
    assert payload["log.original_bytes"] > MAX_LOG_BYTES
    assert payload["persistence.status"] == "error"
    assert payload["http.status"] == 200
    assert payload["request_id"] == "request-large"
    assert "unexpected_payload" not in payload
