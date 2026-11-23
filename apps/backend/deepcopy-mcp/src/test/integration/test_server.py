import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.application import create_server
from app.config.settings import Settings


async def test_public_contract(settings):
    async with Client(create_server(settings)) as client:
        resources = await client.list_resources()
        assert [str(r.uri) for r in resources] == ["guide://deepcopy"]
        guide = (await client.read_resource("guide://deepcopy"))[0].text
        assert "never place" in guide
        assert await client.list_resource_templates() == []
        assert [p.name for p in await client.list_prompts()] == ["review_portfolio"]
        prompt = await client.get_prompt("review_portfolio", {"question": "Cash?"})
        assert "Cash?" in prompt.messages[0].content.text


def test_instructions_describe_the_read_only_scope(settings):
    assert "No tool places orders" in create_server(settings).instructions


async def test_internal_errors_are_masked(api_settings, monkeypatch):
    async def fail(*args):
        raise RuntimeError("private-backend-password")

    monkeypatch.setattr(
        "app.services.portfolio_service.PortfolioService.list_accounts", fail
    )
    async with Client(create_server(api_settings)) as client:
        with pytest.raises(ToolError) as error:
            await client.call_tool("deepcopy_list_accounts", {})
        assert "private-backend-password" not in str(error.value)


async def test_pagination(deepcopy_api):
    server = create_server(
        Settings(_env_file=None, page_size=1, deepcopy_api=deepcopy_api[0])
    )
    async with Client(server) as client:
        first = await client.list_tools_mcp()
        assert len(first.tools) == 1
        assert first.next_cursor
        second = await client.list_tools_mcp(cursor=first.next_cursor)
        assert len(second.tools) == 1
        assert first.tools[0].name != second.tools[0].name
        assert len(await client.list_tools()) == 5


async def test_tool_only_clients():
    server = create_server(
        Settings(
            _env_file=None,
            resources_as_tools=True,
            prompts_as_tools=True,
        )
    )
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
        assert {
            "list_resources",
            "read_resource",
            "list_prompts",
            "get_prompt",
        } <= names
        result = await client.call_tool("read_resource", {"uri": "guide://deepcopy"})
        assert not result.is_error
        result = await client.call_tool(
            "get_prompt",
            {"name": "review_portfolio", "arguments": {"question": "Cash?"}},
        )
        assert not result.is_error
