"""Unit tests for before-agent wide-event enrichment."""

from unittest.mock import MagicMock

from google.adk.agents.callback_context import CallbackContext

from app.components.callbacks.before_agent import record_agent_start
from app.utils.wide_event import wide_event


def should_record_the_started_agent_with_a_structured_log(caplog):
    context = MagicMock(spec=CallbackContext)
    context.agent_name = "market_web_researcher"
    context.invocation_id = "invocation-test"
    context.state = {"analysed_market_data": {"summary": "Test"}}
    scope = wide_event.start({"event": "http.request"})
    try:
        result = record_agent_start(context)
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)

    assert result is None
    assert event["agents.started"] == ["market_web_researcher"]
    assert caplog.records == []


def should_be_a_safe_no_op_outside_a_request():
    context = MagicMock(spec=CallbackContext)
    context.agent_name = "market_web_researcher"

    assert record_agent_start(context) is None
    assert wide_event.current() is None
