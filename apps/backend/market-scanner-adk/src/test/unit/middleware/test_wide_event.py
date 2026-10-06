"""Unit tests for the canonical HTTP wide event."""

import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.wide_event import WideEventMiddleware
from app.utils.wide_event import wide_event


async def _success(_request):
    wide_event.add(action="market_scan.run", **{"scan.asset_count": 12})
    return JSONResponse({"ok": True})


async def _failure(_request):
    raise RuntimeError("provider token must not be copied")


def _application() -> Starlette:
    application = Starlette(
        routes=[
            Route("/run", _success, methods=["POST"]),
            Route("/failure", _failure),
        ]
    )
    application.add_middleware(WideEventMiddleware)
    return application


def _request_events(caplog):
    return [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http.request"
    ]


class TestWideEventMiddleware:
    def should_emit_one_enriched_event_per_request(self, caplog):
        with caplog.at_level(logging.INFO, logger="app.request"):
            response = TestClient(_application()).post(
                "/run", headers={"X-Request-ID": "request-42"}
            )

        assert response.status_code == 200
        assert response.headers["x-request-id"] == "request-42"
        events = _request_events(caplog)
        assert len(events) == 1
        assert events[0].__dict__["action"] == "market_scan.run"
        assert events[0].__dict__["scan.asset_count"] == 12
        assert events[0].__dict__["http.status"] == 200
        assert events[0].__dict__["outcome"] == "success"
        assert events[0].__dict__["http.duration_ms"] >= 0
        assert wide_event.current() is None

    def should_emit_a_safe_error_event_and_reraise(self, caplog):
        client = TestClient(_application(), raise_server_exceptions=False)
        with caplog.at_level(logging.INFO, logger="app.request"):
            response = client.get("/failure")

        event = _request_events(caplog)[0]
        assert response.status_code == 500
        assert event.levelno == logging.ERROR
        assert event.__dict__["outcome"] == "server_error"
        assert event.__dict__["error.kind"] == "RuntimeError"
        assert "error.message" not in event.__dict__


async def _exercise_asgi(app, *, receive=None):
    async def default_receive():
        return {"type": "http.request", "body": b""}

    messages = []

    async def send(message):
        messages.append(message)

    await WideEventMiddleware(app)(
        {"type": "http", "method": "POST", "path": "/run_sse", "headers": []},
        receive or default_receive,
        send,
    )
    return messages


async def should_report_failed_persistence_even_when_http_is_200(caplog):
    async def app(scope, receive, send):
        wide_event.add(**{"persistence.status": "error"})
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {"type": "http.response.body", "body": b'data: {"error":"failed"}\n\n'}
        )

    with caplog.at_level(logging.INFO, logger="app.request"):
        await _exercise_asgi(app)
    record = _request_events(caplog)[0].__dict__
    assert record["http.status"] == 200
    assert record["persistence.status"] == "error"
    assert record["outcome"] == "failed"
    assert record["levelno"] == logging.ERROR


async def should_not_invent_scan_success_when_the_workflow_never_completed(caplog):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {"type": "http.response.body", "body": b'data: {"error":"load failed"}\n\n'}
        )

    with caplog.at_level(logging.INFO, logger="app.request"):
        await _exercise_asgi(app)
    record = _request_events(caplog)[0].__dict__
    assert "scan.status" not in record
    assert record["outcome"] == "success"  # HTTP transport only.


async def should_emit_request_summary_on_cancellation(caplog):
    import asyncio

    caplog.set_level(logging.INFO)
    started = asyncio.Event()

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(_exercise_asgi(app))
    await started.wait()
    assert _request_events(caplog) == []
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancellation was swallowed")

    summaries = _request_events(caplog)
    assert len(summaries) == 1
    record = summaries[0].__dict__
    assert record["http.status"] == 200
    assert record["outcome"] == "cancelled"
    assert wide_event.current() is None


async def should_record_a_disconnect_without_an_exception(caplog):
    async def receive():
        return {"type": "http.disconnect"}

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()

    await _exercise_asgi(app, receive=receive)
    record = _request_events(caplog)[0].__dict__
    assert record["http.response_completed"] is False
    assert record["outcome"] == "cancelled"


async def should_preserve_the_sent_http_status_when_a_stream_raises(caplog):
    import pytest

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("sensitive provider details")

    with pytest.raises(RuntimeError):
        await _exercise_asgi(app)
    record = _request_events(caplog)[0].__dict__
    assert record["http.status"] == 200
    assert record["outcome"] != "success"
    assert "sensitive provider details" not in str(record)
