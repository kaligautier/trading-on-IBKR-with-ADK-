"""Unit tests for the request-scoped wide event."""

from app.utils.wide_event import WideEvent


class TestWideEvent:
    def should_ignore_enrichment_outside_a_request(self):
        event = WideEvent()

        event.add(country="FR")
        event.append("tools.called", "google_search")
        event.increment("tools.count")

        assert event.current() is None
        assert event.request_id() is None

    def should_collect_request_enrichment(self):
        event = WideEvent()
        scope = event.start({"event": "http.request"}, request_id="request-42")
        try:
            event.add(country="FR", ignored=None)
            event.append("tools.called", "google_search")
            event.increment("tools.count", 2)

            assert event.current() == {
                "event": "http.request",
                "request_id": "request-42",
                "country": "FR",
                "tools.called": ["google_search"],
                "tools.count": 2,
            }
            assert event.request_id() == "request-42"
        finally:
            event.reset(scope)

    def should_restore_the_previous_context(self):
        event = WideEvent()
        outer = event.start({"event": "outer"}, request_id="outer-request")
        inner = event.start({"event": "inner"}, request_id="inner-request")

        event.reset(inner)

        assert event.current() == {
            "event": "outer",
            "request_id": "outer-request",
        }
        assert event.request_id() == "outer-request"
        event.reset(outer)

    def should_not_mutate_initial_fields(self):
        event = WideEvent()
        initial = {"event": "http.request"}
        scope = event.start(initial)
        try:
            event.add(outcome="success")
        finally:
            event.reset(scope)

        assert initial == {"event": "http.request"}


def should_bound_request_summary_arrays():
    event = WideEvent()
    scope = event.start()
    try:
        for index in range(105):
            event.append("tools.called", {"index": index})
        assert len(event.current()["tools.called"]) == 100
        assert event.current()["tools.called.dropped"] == 5
    finally:
        event.reset(scope)
