"""Unit tests for tool wide-event enrichment."""

from unittest.mock import MagicMock

from app.components.callbacks.tool_callbacks import record_tool_end, record_tool_start
from app.utils.wide_event import wide_event


def should_record_a_tool_without_its_arguments_or_response(caplog):
    tool = MagicMock(name="tool")
    tool.name = "google_search"
    sensitive_arguments = {"query": "private portfolio details"}
    sensitive_response = {"result": "private result"}
    scope = wide_event.start({"event": "http.request"})
    try:
        before_result = record_tool_start(tool, sensitive_arguments, MagicMock())
        after_result = record_tool_end(
            tool,
            sensitive_arguments,
            MagicMock(),
            sensitive_response,
        )
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)

    assert before_result is None
    assert after_result is None
    assert event["tools.called"] == ["google_search"]
    assert event["tools.completed"] == ["google_search"]
    assert "private" not in str(event)
    assert caplog.records == []
