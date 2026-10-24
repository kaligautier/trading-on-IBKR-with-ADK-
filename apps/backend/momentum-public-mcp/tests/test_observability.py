"""Trace a real MCP request through its adapter without logging private data."""

import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult
from starlette.testclient import TestClient
from test_gateway import gateway_with, market_scan
from test_server import StaticFingerprint
from test_stateless_http import envelope, headers

from momentum_public_mcp.observability import JsonFormatter, ToolTelemetry
from momentum_public_mcp.protocol import create_http_app
from momentum_public_mcp.server import MomentumPublicMcpServer
from momentum_public_mcp.tools import MomentumPublicTools


@pytest.mark.parametrize("upstream_status", [200, 503])
def test_tool_and_upstream_share_trace_and_track_tool_errors(caplog, upstream_status):
    calls = []

    async def upstream(request):
        calls.append(request)
        return httpx.Response(upstream_status, json=market_scan())

    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway_with(upstream), StaticFingerprint())
    ).server
    parent_trace = "1" * 32
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")
    with TestClient(create_http_app(server)) as client:
        responses = [
            client.post(
                "/",
                headers={
                    **headers("tools/call", "latest_market_scan"),
                    "traceparent": f"00-{parent_trace}-{'2' * 16}-01",
                    "X-Request-ID": "untrusted-caller-value",
                },
                json=envelope("tools/call", name="latest_market_scan", arguments={}),
            )
            for _ in range(2)
        ]
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
    assert len(events) == 6
    for identifier in ids:
        correlated = [
            event for event in events if event["correlation_id"] == identifier
        ]
        assert {event["event"] for event in correlated} == {
            "http_request",
            "tool_call",
            "upstream_request",
        }
        assert all(event["trace_id"] == parent_trace for event in correlated)
        tool = next(event for event in correlated if event["event"] == "tool_call")
        assert tool["outcome"] == ("error" if upstream_status == 503 else "success")
        assert tool["duration_ms"] >= 0
    assert {request.headers["x-request-id"] for request in calls} == ids
    assert all(
        request.headers["traceparent"].split("-")[1] == parent_trace
        for request in calls
    )


async def test_explicit_error_result_is_not_counted_as_success(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.telemetry")

    async def next_handler(context):
        return ToolResult(content="private result", is_error=True)

    result = await ToolTelemetry().on_call_tool(
        MiddlewareContext(message=SimpleNamespace(name="list_analyses")), next_handler
    )
    assert result.is_error
    assert caplog.records[-1].event_fields["outcome"] == "error"
    assert "private result" not in JsonFormatter().format(caplog.records[-1])


def test_formatter_omits_third_party_payload_and_exception_text():
    record = logging.LogRecord(
        "fastmcp", logging.ERROR, "", 1, "token=private", (), None
    )
    value = json.loads(JsonFormatter().format(record))
    assert value == {"severity": "ERROR", "logger": "fastmcp", "event": "runtime_log"}
