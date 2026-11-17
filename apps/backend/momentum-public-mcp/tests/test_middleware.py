"""Tests for MCP request logging and argument redaction."""

import logging
from types import SimpleNamespace

from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools import ToolResult

from momentum_public_mcp.middleware import ToolCallLoggingMiddleware


async def test_logs_bounded_arguments_and_redacts_sensitive_fields(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.middleware.logging")
    arguments = {
        "page_size": 5,
        "page_token": "opaque-cursor",
        "credentials": {"api-key": "private-key"},
        "reason": "x" * 300,
        "symbol": "y" * 300,
    }
    context = MiddlewareContext(
        message=SimpleNamespace(
            name="momentum_list_analyses",
            arguments=arguments,
        )
    )

    async def call_next(_context):
        return ToolResult(content="private result")

    result = await ToolCallLoggingMiddleware().on_call_tool(context, call_next)

    assert not result.is_error
    record = caplog.records[-1].event_fields
    assert record["event"] == "tool_call"
    assert record["tool"] == "momentum_list_analyses"
    assert record["arguments"]["page_size"] == 5
    assert record["arguments"]["page_token"] == "[REDACTED]"
    assert record["arguments"]["credentials"]["api-key"] == "[REDACTED]"
    assert record["arguments"]["reason"] == "[OMITTED 300 chars]"
    assert record["arguments"]["symbol"].endswith("…[TRUNCATED]")
    assert "private result" not in caplog.text


async def test_never_logs_free_text_reason(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.middleware.logging")
    context = MiddlewareContext(
        message=SimpleNamespace(
            name="momentum_suggest_ticker",
            arguments={"symbol": "AAPL", "reason": "my password is hunter2"},
        )
    )

    async def call_next(_context):
        return ToolResult(content="ok")

    await ToolCallLoggingMiddleware().on_call_tool(context, call_next)

    record = caplog.records[-1].event_fields
    assert record["arguments"] == {"symbol": "AAPL", "reason": "[OMITTED 22 chars]"}
    assert "hunter2" not in caplog.text


async def test_logs_exception_type_without_exception_message(caplog):
    caplog.set_level(logging.INFO, logger="momentum_public_mcp.middleware.logging")
    context = MiddlewareContext(
        message=SimpleNamespace(name="momentum_list_analyses", arguments={})
    )

    async def call_next(_context):
        raise RuntimeError("private upstream response")

    try:
        await ToolCallLoggingMiddleware().on_call_tool(context, call_next)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Tool call exception was swallowed")

    record = caplog.records[-1].event_fields
    assert record["outcome"] == "error"
    assert record["error_type"] == "RuntimeError"
    assert "private upstream response" not in caplog.text
