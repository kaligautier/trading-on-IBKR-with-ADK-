"""MCP message logs preserve native results, errors and per-caller rate limits."""

import json
import logging

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from mcp.types import CallToolRequestParams
from pythonjsonlogger.json import JsonFormatter
from starlette.testclient import TestClient
from test_server import StaticFingerprint, StubGateway
from test_stateless_http import envelope, headers

from app.core_components.resources.public_resources import MomentumPublicResources
from app.core_components.tools.public_tools import MomentumPublicTools
from app.middleware.logging import RequestLoggingMiddleware
from app.protocol import create_http_app
from app.server import MomentumPublicMcpServer

LOGGER = "app.middleware.logging"


def server_with(fingerprint=None):
    gateway = StubGateway()
    return MomentumPublicMcpServer(
        MomentumPublicTools(gateway, fingerprint or StaticFingerprint()),
        fingerprint=fingerprint,
        resources=MomentumPublicResources(gateway),
    ).server


def messages(caplog):
    return [record.getMessage() for record in caplog.records if record.name == LOGGER]


def json_records(caplog):
    formatter = JsonFormatter()
    return [
        json.loads(formatter.format(record))
        for record in caplog.records
        if record.name == LOGGER
    ]


@pytest.mark.parametrize(
    "method",
    [
        "server/discover",
        "tools/list",
        "resources/list",
        "resources/templates/list",
        "prompts/list",
    ],
)
def test_each_message_is_logged_once_with_native_duration(caplog, method):
    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        TestClient(create_http_app(server_with())) as client,
    ):
        response = client.post("/", headers=headers(method), json=envelope(method))
        assert response.status_code == 200
        assert "result" in response.json()
        assert len(messages(caplog)) == 2
        start, end = messages(caplog)
        assert f"event=request_start method={method} source=client" in start
        assert f"event=request_success method={method} source=client" in end
        assert "duration_ms=" in end
        client.get("/health")
        assert len(messages(caplog)) == 2


@pytest.mark.parametrize(
    "arguments",
    [
        {"page_token": "private-cursor-marker" * 40},
        {"unexpected": "ordinary-argument-value"},
        {
            "unexpected": [
                {"Password": "private-cursor-marker"},
                {"nested": {"API-Key": "private-cursor-marker"}},
            ],
        },
        {"page_size": 555},
    ],
)
def test_validation_errors_propagate_with_sensitive_fields_masked(caplog, arguments):
    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        TestClient(create_http_app(server_with())) as client,
    ):
        response = client.post(
            "/",
            headers=headers("tools/call", "momentum_get_recommendations"),
            json=envelope(
                "tools/call", name="momentum_get_recommendations", arguments=arguments
            ),
        )
    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True
    # FastMCP may also discover tools to populate its HTTP routing metadata.
    records = [line for line in messages(caplog) if "method=tools/call " in line]
    assert len(records) == 2
    assert "event=request_error" in records[-1]
    assert "duration_ms=" in records[-1]
    all_messages = json.dumps(json_records(caplog))
    assert "private-cursor-marker" not in all_messages
    assert "errors.pydantic.dev" not in all_messages
    assert "payload=" not in all_messages


def test_tool_hook_logs_parameters_without_changing_forwarded_cursor(
    caplog, monkeypatch
):
    received_tokens = []
    original = StubGateway.list_analyses

    async def capture_arguments(self, ticker, page):
        received_tokens.append(page.page_token)
        return await original(self, ticker, page)

    monkeypatch.setattr(StubGateway, "list_analyses", capture_arguments)
    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        TestClient(create_http_app(server_with())) as client,
    ):
        response = client.post(
            "/",
            headers=headers("tools/call", "momentum_list_analyses"),
            json=envelope(
                "tools/call",
                name="momentum_list_analyses",
                arguments={
                    "ticker": "AAPL",
                    "page_size": 1,
                    "page_token": "private-cursor-marker",
                },
            ),
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"]["items"][0]["ticker"] == "AAPL"
    tool_records = [
        record
        for record in json_records(caplog)
        if "event=tool_call " in record["message"]
    ]
    assert len(tool_records) == 1
    record = tool_records[0]
    assert record["tool"] == "momentum_list_analyses"
    assert "argument_count=3" in record["message"]
    assert record["arguments"] == {
        "ticker": "AAPL",
        "page_size": 1,
        "page_token": "[REDACTED]",
    }
    assert "private-cursor-marker" not in json.dumps(json_records(caplog))
    assert received_tokens == ["private-cursor-marker"]


def test_malformed_request_is_observed_before_tool_dispatch(caplog):
    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        TestClient(create_http_app(server_with())) as client,
    ):
        response = client.post(
            "/", headers=headers("tools/call"), json=envelope("tools/call")
        )
    assert response.status_code == 400
    assert "error" in response.json()
    assert len(messages(caplog)) == 2
    assert "event=request_error" in messages(caplog)[-1]


async def test_notification_needs_no_session_and_has_no_response(caplog):
    context = MiddlewareContext(
        method="notifications/initialized",
        type="notification",
        message={"private": "private-notification-marker"},
    )
    calls = []

    async def next_handler(actual):
        calls.append(actual)
        return None

    with caplog.at_level(logging.INFO, logger=LOGGER):
        result = await RequestLoggingMiddleware()(context, next_handler)
    assert result is None
    assert calls == [context]
    assert len(messages(caplog)) == 2
    assert "event=notification_success" in messages(caplog)[-1]
    assert "private-notification-marker" not in " ".join(messages(caplog))


async def test_error_keeps_its_identity_and_cause(caplog):
    cause = ValueError("private-exception-marker")
    failure = ToolError("public message")
    failure.__cause__ = cause
    context = MiddlewareContext(
        method="tools/call",
        message=CallToolRequestParams(name="momentum_list_analyses"),
    )

    async def next_handler(actual):
        raise failure

    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        pytest.raises(ToolError) as error,
    ):
        await RequestLoggingMiddleware()(context, next_handler)
    assert error.value is failure
    assert error.value.__cause__ is cause
    assert "error=ToolError" in messages(caplog)[-1]
    assert "private-exception-marker" not in " ".join(messages(caplog))


def test_rate_limit_rejections_are_logged_and_callers_are_independent(caplog):
    class Fingerprint:
        value = "private-first-caller"

        def current(self):
            return self.value

    fingerprint = Fingerprint()
    server = server_with(fingerprint)
    limiter = next(
        item
        for item in server.middleware
        if isinstance(item, SlidingWindowRateLimitingMiddleware)
    )
    assert limiter.max_requests == 60
    assert limiter.window_seconds == 60
    with (
        caplog.at_level(logging.INFO, logger=LOGGER),
        TestClient(create_http_app(server)) as client,
    ):
        for _ in range(60):
            response = client.post("/", headers=headers(), json=envelope())
            assert "result" in response.json()
        blocked = client.post("/", headers=headers(), json=envelope())
        assert blocked.json()["error"]["code"] == -32000
        assert "Rate limit exceeded" in blocked.text
        assert "error=RateLimitError" in messages(caplog)[-1]
        assert "private-first-caller" not in " ".join(messages(caplog))
        fingerprint.value = "second-caller"
        accepted = client.post("/", headers=headers(), json=envelope())
        assert "result" in accepted.json()
