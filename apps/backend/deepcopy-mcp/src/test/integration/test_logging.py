"""Exercise native request logging through the MCP client boundary."""

import logging

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.application import create_server
from app.config.settings import Settings

LOGGER = "app.mcp.requests"


def request_messages(caplog):
    return [record.getMessage() for record in caplog.records if record.name == LOGGER]


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_logs_tool_arguments_and_completion(api_settings, caplog, mode):
    caplog.set_level(logging.INFO, logger=LOGGER)
    async with Client(create_server(api_settings), mode=mode) as client:
        await client.list_tools()
        assert not request_messages(caplog)
        result = await client.call_tool(
            "deepcopy_get_positions", {"account_id": "U1234567", "page": 0}
        )
    messages = request_messages(caplog)
    assert result.structured_content["result"][0]["symbol"] == "AAPL"
    assert len(messages) == 2
    assert "event=request_start" in messages[0]
    assert '"name":"deepcopy_get_positions"' in messages[0]
    assert '"arguments":{"account_id":"U1234567","page":0}' in messages[0]
    assert "event=request_success" in messages[1]
    assert "duration_ms=" in messages[1]


async def test_arguments_can_be_disabled(deepcopy_api, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    settings = Settings(
        _env_file=None, log_tool_arguments=False, deepcopy_api=deepcopy_api[0]
    )
    async with Client(create_server(settings)) as client:
        await client.call_tool(
            "deepcopy_get_account_summary", {"account_id": "U7654321"}
        )
    messages = request_messages(caplog)
    assert len(messages) == 2
    assert "payload=" not in " ".join(messages)
    assert "U7654321" not in " ".join(messages)


async def test_request_payload_is_truncated(deepcopy_api, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    settings = Settings(
        _env_file=None, log_max_payload_length=20, deepcopy_api=deepcopy_api[0]
    )
    async with Client(create_server(settings)) as client:
        await client.call_tool("deepcopy_search_contracts", {"symbol": "AAPL"})
    start = request_messages(caplog)[0]
    payload = start.split("payload=", 1)[1].split(" payload_type=", 1)[0]
    assert len(payload) == 23
    assert payload.endswith("...")


async def test_errors_are_logged_and_remain_tool_errors(api_settings, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    async with Client(create_server(api_settings)) as client:
        with pytest.raises(ToolError, match="not ready"):
            await client.call_tool(
                "deepcopy_get_account_summary", {"account_id": "DOWN"}
            )
    messages = request_messages(caplog)
    assert len(messages) == 2
    assert "event=request_error" in messages[1]
    assert "duration_ms=" in messages[1]
