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


class TestCloudLoggingFields:
    def should_expose_severity_for_cloud_logging(self):
        payload = json.loads(JsonFormatter().format(_record()))

        assert payload["severity"] == "INFO"
        assert payload["level"] == "INFO"

    def should_link_the_entry_to_the_caller_trace(self, monkeypatch):
        from app.config.settings import settings
        from app.utils.trace_context import TraceContext

        monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "example-project")
        trace = TraceContext.from_traceparent(
            "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"
        )
        scope = wide_event.start({}, request_id="request-42", trace=trace)
        try:
            payload = json.loads(JsonFormatter().format(_record()))
        finally:
            wide_event.reset(scope)

        assert payload["trace_id"] == "1234567890abcdef1234567890abcdef"
        assert payload["logging.googleapis.com/trace"] == (
            "projects/example-project/traces/1234567890abcdef1234567890abcdef"
        )
        assert payload["logging.googleapis.com/spanId"] == "1234567890abcdef"
        assert payload["logging.googleapis.com/trace_sampled"] is True

    def should_omit_trace_fields_outside_a_traced_request(self):
        payload = json.loads(JsonFormatter().format(_record()))

        assert "trace_id" not in payload
        assert "logging.googleapis.com/trace" not in payload
