"""Trace a real MCP request through its adapter without logging private data."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult
from starlette.testclient import TestClient
from test_gateway import analysis_summary, gateway_with, market_scan
from test_server import StaticFingerprint
from test_stateless_http import envelope, headers

from momentum_public_mcp.observability import (
    CanonicalRequestFilter,
    JsonFormatter,
    RequestTelemetry,
    ToolTelemetry,
    request_event,
)
from momentum_public_mcp.protocol import create_http_app
from momentum_public_mcp.server import MomentumPublicMcpServer
from momentum_public_mcp.tools import MomentumPublicTools


@pytest.mark.parametrize("upstream_status", [200, 503])
def test_tool_and_upstream_share_trace_and_track_tool_errors(caplog, upstream_status):
    calls = []

    async def upstream(request):
        calls.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(upstream_status, json=market_scan())

    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway_with(upstream), StaticFingerprint())
    ).server
    parent_trace = "1" * 32
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")
    with TestClient(create_http_app(server)) as client:

        def call(_):
            return client.post(
                "/",
                headers={
                    **headers("tools/call", "latest_market_scan"),
                    "traceparent": f"00-{parent_trace}-{'2' * 16}-01",
                    "X-Request-ID": "untrusted-caller-value",
                },
                json=envelope("tools/call", name="latest_market_scan", arguments={}),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(call, range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert all(
        bool(response.json()["result"].get("isError")) == (upstream_status == 503)
        for response in responses
    )
    ids = {response.headers["x-request-id"] for response in responses}
    assert len(ids) == 2 and "untrusted-caller-value" not in ids
    events = [
        record.event_fields
        for record in caplog.records
        if hasattr(record, "event_fields")
    ]
    assert len(events) == 2
    for identifier in ids:
        correlated = [
            event for event in events if event["correlation_id"] == identifier
        ]
        assert len(correlated) == 1
        event = correlated[0]
        assert event["event"] == "request_completed"
        assert event["trace_id"] == parent_trace
        assert event["http"]["status"] == 200
        assert event["tool"]["name"] == "latest_market_scan"
        assert event["outcome"] == ("error" if upstream_status == 503 else "success")
        assert event["duration_ms"] >= event["tool"]["duration_ms"]
        assert event["upstreams"]["scanner"]["calls"] == 1
        assert event["upstreams"]["scanner"]["last_status"] == upstream_status
        if upstream_status == 200:
            assert event["business"]["asset_count"] == len(
                market_scan()["report"]["assets"]
            )
    assert {request.headers["x-request-id"] for request in calls} == ids
    assert all(
        request.headers["traceparent"].split("-")[1] == parent_trace
        for request in calls
    )


async def test_explicit_error_result_is_not_counted_as_success(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")

    async def next_handler(context):
        return ToolResult(content="private result", is_error=True)

    async def app(scope, receive, send):
        result = await ToolTelemetry().on_call_tool(
            MiddlewareContext(message=SimpleNamespace(name="list_analyses")),
            next_handler,
        )
        assert result.is_error
        await send({"type": "http.response.start", "status": 200})

    async def discard(message):
        pass

    await RequestTelemetry(app, success_sample_rate=0)(
        {"type": "http", "method": "POST", "path": "/"}, None, discard
    )
    assert caplog.records[-1].event_fields["outcome"] == "error"
    assert "private result" not in JsonFormatter().format(caplog.records[-1])


def test_formatter_omits_third_party_payload_and_exception_text():
    record = logging.LogRecord(
        "fastmcp", logging.ERROR, "", 1, "token=private", (), None
    )
    value = json.loads(JsonFormatter().format(record))
    assert value == {"severity": "ERROR", "logger": "fastmcp", "event": "runtime_log"}


@pytest.mark.parametrize(
    "status,rate,slow,retained",
    [
        (200, 0, False, False),
        (200, 1, False, True),
        (200, 0, True, True),
        (429, 0, False, True),
        (500, 0, False, True),
    ],
)
async def test_tail_sampling_preserves_failures_and_slow_requests(
    caplog, status, rate, slow, retained
):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")

    async def app(scope, receive, send):
        if slow:
            await asyncio.sleep(0.01)
        await send({"type": "http.response.start", "status": status})

    async def discard(message):
        pass

    await RequestTelemetry(app, success_sample_rate=rate, slow_request_ms=5)(
        {"type": "http", "method": "POST", "path": "/"}, None, discard
    )
    events = [
        record.event_fields
        for record in caplog.records
        if hasattr(record, "event_fields")
    ]
    assert len(events) == int(retained)
    if retained:
        assert events[0]["sample_rate"] == 1
    assert request_event.get() is None


async def test_cancellation_emits_once_and_clears_context(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")

    async def app(scope, receive, send):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await RequestTelemetry(app, success_sample_rate=0)(
            {"type": "http", "method": "POST", "path": "/"}, None, None
        )
    events = [
        record.event_fields
        for record in caplog.records
        if hasattr(record, "event_fields")
    ]
    assert len(events) == 1 and events[0]["error_type"] == "CancelledError"
    assert request_event.get() is None


def test_library_chatter_is_suppressed_only_inside_requests():
    record = logging.LogRecord("httpx", logging.INFO, "", 1, "private-url", (), None)
    policy = CanonicalRequestFilter()
    assert policy.filter(record)
    token = request_event.set({})
    try:
        assert not policy.filter(record)
        record.event_fields = {"event": "request_completed"}
        assert policy.filter(record)
    finally:
        request_event.reset(token)


def test_paginated_api_calls_are_summarized_in_one_event(caplog):
    calls = []

    async def upstream(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "items": [analysis_summary()],
                "next_page_token": str(len(calls)) if len(calls) < 3 else "",
            },
        )

    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway_with(upstream), StaticFingerprint())
    ).server
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")
    with TestClient(create_http_app(server)) as client:
        response = client.post(
            "/",
            headers=headers("tools/call", "list_analyses"),
            json=envelope("tools/call", name="list_analyses", arguments={"limit": 3}),
        )
    assert not response.json()["result"]["isError"]
    events = [
        record.event_fields
        for record in caplog.records
        if hasattr(record, "event_fields")
    ]
    assert len(events) == 1
    assert events[0]["upstreams"]["momentum"]["calls"] == len(calls) == 3
    assert events[0]["business"] == {"result_count": 3}
