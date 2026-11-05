"""JSON log formatting with the active OpenTelemetry span context."""

import json
import logging

from app.config.config import Settings
from app.config.constants import NOISY_LOGGERS
from app.observability.logger import TraceInjectFilter, config_logger


def test_filter_uses_empty_ids_outside_a_trace():
    record = logging.LogRecord("app", logging.INFO, "", 1, "Ready", (), None)
    assert TraceInjectFilter().filter(record)
    assert record.trace_id == record.span_id == ""


def test_configured_handler_preserves_message_and_active_trace(monkeypatch, tracing):
    configured = {}
    monkeypatch.setattr(
        logging, "basicConfig", lambda **kwargs: configured.update(kwargs)
    )
    for name in NOISY_LOGGERS:
        noisy = logging.getLogger(name)
        monkeypatch.setattr(noisy, "level", noisy.level)
    settings = Settings(
        _env_file=None, SUGGESTION_HASH_SECRET="test-secret", LOG_LEVEL="DEBUG"
    )
    config_logger(settings)
    assert configured["level"] == "DEBUG" and configured["force"] is True
    assert all(
        logging.getLogger(name).level == logging.WARNING for name in NOISY_LOGGERS
    )
    handler = configured["handlers"][0]
    provider, _ = tracing
    with provider.get_tracer("test").start_as_current_span("log-check") as span:
        record = logging.LogRecord(
            "app.test",
            logging.INFO,
            "test.py",
            1,
            "Ready %s",
            ("now",),
            None,
            "start",
        )
        assert handler.filter(record)
        fields = json.loads(handler.format(record))
        assert fields["severity"] == "INFO"
        assert fields["message"] == "Ready now"
        assert fields["module"] == "test" and fields["funcName"] == "start"
        assert fields["trace_id"] == format(span.get_span_context().trace_id, "032x")
        assert fields["span_id"] == format(span.get_span_context().span_id, "016x")
    handler.close()
