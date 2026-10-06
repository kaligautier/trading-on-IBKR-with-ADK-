"""Unit tests for after-agent wide-event enrichment."""

from unittest.mock import MagicMock

from google.adk.agents.callback_context import CallbackContext

from app.components.callbacks.after_agent import record_agent_end
from app.utils.wide_event import wide_event


def should_record_the_completed_agent_with_a_structured_log(caplog):
    context = MagicMock(spec=CallbackContext)
    context.agent_name = "market_synthesizer"
    context.invocation_id = "invocation-test"
    context.state = {"market_analysis": {"summary": "Test"}}
    scope = wide_event.start({"event": "http.request"})
    try:
        result = record_agent_end(context)
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)

    assert result is None
    assert event["agents.completed"] == ["market_synthesizer"]
    assert caplog.records == []
