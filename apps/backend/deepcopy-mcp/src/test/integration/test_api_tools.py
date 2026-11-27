"""Actual sockets exercise HTTPX, not a stubbed transport or service."""

import time

import pytest
from conftest import ACCOUNT, CONTRACT, POSITION, SESSION, TOKEN, deepcopy_upstream
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.api.config import create_http_client
from app.application import create_server
from app.config.settings import Settings

TOOLS = {
    "deepcopy_get_session": "Get IBKR session",
    "deepcopy_list_accounts": "List IBKR accounts",
    "deepcopy_get_account_summary": "Get IBKR account summary",
    "deepcopy_get_positions": "Get IBKR positions",
    "deepcopy_search_contracts": "Search IBKR contracts",
}


async def test_tools_are_read_only_and_described(api_settings):
    async with Client(create_server(api_settings)) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == set(TOOLS)
    for name, title in TOOLS.items():
        annotations = tools[name].annotations
        assert annotations.title == title
        assert annotations.read_only_hint is True
        assert annotations.destructive_hint is False
        assert annotations.idempotent_hint is True
        assert annotations.open_world_hint is True
        assert tools[name].output_schema
        assert all(
            prop.get("description")
            for prop in tools[name].input_schema.get("properties", {}).values()
        )


async def test_tools_return_typed_results(deepcopy_api, api_settings, caplog):
    caplog.set_level("INFO", logger="app.mcp.requests")
    _, calls = deepcopy_api
    async with Client(create_server(api_settings)) as client:
        session = await client.call_tool("deepcopy_get_session", {})
        accounts = await client.call_tool("deepcopy_list_accounts", {})
        summary = await client.call_tool(
            "deepcopy_get_account_summary", {"account_id": "U1234567"}
        )
        positions = await client.call_tool(
            "deepcopy_get_positions", {"account_id": "U1234567", "page": 2}
        )
        contracts = await client.call_tool(
            "deepcopy_search_contracts", {"symbol": "AAPL"}
        )
    assert session.structured_content == SESSION
    assert accounts.structured_content == {"result": [ACCOUNT]}
    assert summary.structured_content["net_liquidation"] == 1000.0
    assert summary.structured_content["gross_position_value"] is None
    assert positions.structured_content["result"][0]["quantity"] == POSITION["quantity"]
    assert contracts.structured_content == {"result": [CONTRACT]}
    assert [path for path, _ in calls] == [
        "/v1/ibkr/session",
        "/v1/ibkr/accounts",
        "/v1/ibkr/accounts/U1234567/summary",
        "/v1/ibkr/accounts/U1234567/positions?page=2",
        "/v1/ibkr/contracts?symbol=AAPL",
    ]
    assert all(headers["Authorization"] == f"Bearer {TOKEN}" for _, headers in calls)
    assert all("Cookie" not in headers for _, headers in calls)
    assert TOKEN not in caplog.text


async def test_tools_are_absent_without_configuration(settings):
    async with Client(create_server(settings)) as client:
        assert await client.list_tools() == []


@pytest.mark.parametrize(
    "account_id,message",
    [
        ("MISSING", "not found"),
        ("AUTH", "rejected credentials"),
        ("FORBIDDEN", "rejected credentials"),
        ("BADINPUT", "invalid request"),
        ("LIMITED", "rate limit"),
        ("DOWN", "not ready"),
        ("REDIRECT", "unavailable"),
        ("BADJSON", "invalid data"),
        ("INVALID", "invalid data"),
        ("WRONG", "different account"),
        ("HUGE", "too large"),
        ("COMPRESSED", "unsupported encoding"),
    ],
)
async def test_upstream_failures_are_safe_and_not_retried(
    deepcopy_api, api_settings, account_id, message, caplog
):
    _, calls = deepcopy_api
    async with Client(create_server(api_settings)) as client:
        with pytest.raises(ToolError, match=message) as error:
            await client.call_tool(
                "deepcopy_get_account_summary", {"account_id": account_id}
            )
        assert "private-backend-detail" not in str(error.value) + caplog.text
        assert TOKEN not in str(error.value) + caplog.text
        assert len(calls) == 1
        assert not (await client.call_tool("deepcopy_list_accounts", {})).is_error


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("deepcopy_get_account_summary", {"account_id": "../secret"}),
        ("deepcopy_get_account_summary", {"account_id": "u1234567"}),
        ("deepcopy_get_account_summary", {"account_id": "U1?page=1"}),
        ("deepcopy_get_account_summary", {"account_id": "U" * 21}),
        ("deepcopy_get_account_summary", {"account_id": ""}),
        ("deepcopy_get_positions", {"account_id": "U1", "page": -1}),
        ("deepcopy_get_positions", {"account_id": "U1", "page": "1"}),
        ("deepcopy_search_contracts", {"symbol": "aapl"}),
        ("deepcopy_search_contracts", {"symbol": "AAPL&x=1"}),
        ("deepcopy_search_contracts", {"symbol": "A" * 13}),
    ],
)
async def test_invalid_arguments_never_reach_the_upstream(
    deepcopy_api, api_settings, tool, arguments
):
    _, calls = deepcopy_api
    async with Client(create_server(api_settings)) as client:
        with pytest.raises(ToolError):
            await client.call_tool(tool, arguments)
    assert not calls


@pytest.mark.parametrize(
    "account_id,limits",
    [
        ("SLOW", {"read_timeout_seconds": 0.03}),
        ("DRIP", {"request_timeout_seconds": 0.08, "read_timeout_seconds": 0.2}),
    ],
)
async def test_read_and_total_timeout_release_the_connection(
    deepcopy_api, account_id, limits
):
    config, calls = deepcopy_api
    settings = Settings(deepcopy_api={**config, **limits, "max_connections": 1})
    async with Client(create_server(settings)) as client:
        start = time.monotonic()
        with pytest.raises(ToolError, match="timed out"):
            await client.call_tool(
                "deepcopy_get_account_summary", {"account_id": account_id}
            )
        assert time.monotonic() - start < 1
        assert not (await client.call_tool("deepcopy_list_accounts", {})).is_error
    assert len(calls) == 2


async def test_connection_failure_is_a_tool_error():
    # Use a just-closed local listener, not a provider or a routable external host.
    with deepcopy_upstream() as (config, _):
        pass
    async with Client(create_server(Settings(deepcopy_api=config))) as client:
        with pytest.raises(ToolError, match="unavailable"):
            await client.call_tool("deepcopy_list_accounts", {})


async def test_lifespan_closes_and_reuses_the_client(api_settings, monkeypatch):
    clients = []

    def capture(config):
        client = create_http_client(config)
        clients.append(client)
        return client

    monkeypatch.setattr(
        "app.api.deepcopy.config.client_config.create_http_client", capture
    )
    async with Client(create_server(api_settings)) as client:
        for _ in range(2):
            await client.call_tool("deepcopy_list_accounts", {})
        with pytest.raises(ToolError):
            await client.call_tool(
                "deepcopy_get_account_summary", {"account_id": "DOWN"}
            )
        assert len(clients) == 1
        assert not clients[0].is_closed
    assert clients[0].is_closed


async def test_typed_client_works_without_mcp(deepcopy_api):
    from app.api.deepcopy.config.client_config import create_deepcopy_client
    from app.api.deepcopy.config.settings import DeepcopyApiSettings
    from app.api.deepcopy.dtos.request.account_request import GetPositionsRequest
    from app.api.deepcopy.dtos.response.portfolio_responses import PositionsResponse

    config, calls = deepcopy_api
    async with create_deepcopy_client(
        DeepcopyApiSettings.model_validate(config)
    ) as client:
        positions = await client.get_positions(
            GetPositionsRequest(account_id="U7654321")
        )
    assert isinstance(positions, PositionsResponse)
    assert positions.root[0].conid == POSITION["conid"]
    assert [path for path, _ in calls] == [
        "/v1/ibkr/accounts/U7654321/positions?page=0"
    ]
