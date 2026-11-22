"""Unit tests for W3C trace context parsing."""

import pytest

from app.utils.trace_context import TraceContext

TRACE = "1234567890abcdef1234567890abcdef"
SPAN = "1234567890abcdef"


def should_read_a_sampled_version_00_traceparent():
    trace = TraceContext.from_traceparent(f"00-{TRACE}-{SPAN}-01")

    assert trace == TraceContext(trace_id=TRACE, span_id=SPAN, sampled=True)


def should_read_an_unsampled_traceparent():
    trace = TraceContext.from_traceparent(f"00-{TRACE}-{SPAN}-00")

    assert trace is not None
    assert trace.sampled is False


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        f"01-{TRACE}-{SPAN}-01",
        f"00-{'0' * 32}-{SPAN}-01",
        f"00-{TRACE}-{'0' * 16}-01",
        f"00-{TRACE.upper()}-{SPAN}-01",
        f"00-{TRACE}-{SPAN}-01-extra",
    ],
)
def should_ignore_invalid_traceparent(value):
    assert TraceContext.from_traceparent(value) is None


def should_only_build_cloud_logging_links_with_a_project():
    trace = TraceContext(trace_id=TRACE, span_id=SPAN, sampled=False)

    assert trace.log_fields("") == {"trace_id": TRACE}
    assert trace.log_fields("p")["logging.googleapis.com/trace"] == (
        f"projects/p/traces/{TRACE}"
    )
