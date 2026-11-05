"""MCP tools preserve API cursor pages without implicit HTTP traversal."""

import httpx
import pytest
from fastmcp import Client
from test_gateway import analysis_summary, gateway_with
from test_server import StaticFingerprint

from app.core_components.resources.public_resources import MomentumPublicResources
from app.core_components.tools.public_tools import MomentumPublicTools
from app.domain import AnalysisPage
from app.server import MomentumPublicMcpServer

OPERATIONS = [
    (
        "momentum_list_analyses",
        "/v1/analyses",
        {"ticker": " aapl "},
        {"ticker": "AAPL"},
        50,
        100,
    ),
    (
        "momentum_latest_analyses",
        "/v1/analyses/latest",
        {"rating": " buy, OVERWEIGHT "},
        {"rating": "Buy,Overweight"},
        50,
        100,
    ),
    (
        "momentum_get_recommendations",
        "/v1/recommendations",
        {},
        {"rating": "Buy,Overweight"},
        10,
        50,
    ),
]


@pytest.fixture(params=OPERATIONS, ids=[operation[0] for operation in OPERATIONS])
def operation(request):
    return request.param


@pytest.fixture
async def connection():
    requests = []
    replies = []

    def handler(request):
        requests.append(request)
        assert replies, "Unexpected extra upstream request"
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    gateway = gateway_with(handler)
    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway, StaticFingerprint()),
        resources=MomentumPublicResources(gateway),
    ).server
    try:
        async with Client(server) as client:
            yield client, requests, replies
    finally:
        await gateway.close()


@pytest.mark.parametrize("first_count", [0, 1])
async def test_client_controls_each_page_and_preserves_opaque_api_cursors(
    connection, operation, first_count
):
    client, requests, replies = connection
    name, endpoint, arguments, filters, _, _ = operation
    tokens = ["", "opaque:+/token=", "x" * 512, ""]
    collected = []
    for index, count in enumerate([first_count, 2, 2]):
        items = [
            {
                **analysis_summary(),
                "id": f"{index * 2 + item + 1:08d}-1111-1111-1111-111111111111",
            }
            for item in range(count)
        ]
        replies.append(
            httpx.Response(
                200, json={"items": items, "next_page_token": tokens[index + 1]}
            )
        )
        result = await client.call_tool(
            name, {**arguments, "page_size": 2, "page_token": tokens[index]}
        )
        assert not result.is_error
        assert len(requests) == index + 1
        assert requests[-1].url.path == endpoint
        assert dict(requests[-1].url.params) == {
            **filters,
            "page_size": "2",
            "page_token": tokens[index],
        }
        content = result.structured_content
        assert set(content) == {"items", "next_page_token"}
        assert [item["id"] for item in content["items"]] == [
            item["id"] for item in items
        ]
        assert content["next_page_token"] == tokens[index + 1]
        collected.extend(item["id"] for item in content["items"])
    assert len(collected) == len(set(collected)) == 4 + first_count


async def test_default_page_size_filters_and_empty_catalog(connection, operation):
    client, requests, replies = connection
    name, endpoint, arguments, filters, default_size, _ = operation
    replies.append(httpx.Response(200, json={"items": [], "next_page_token": ""}))
    result = await client.call_tool(name, arguments)
    assert not result.is_error
    assert result.structured_content == {"items": [], "next_page_token": ""}
    assert len(requests) == 1
    assert requests[0].url.path == endpoint
    assert dict(requests[0].url.params) == {
        **filters,
        "page_size": str(default_size),
        "page_token": "",
    }


@pytest.mark.parametrize("boundary", ["minimum", "maximum"])
async def test_accepts_page_size_boundaries_and_a_full_final_page(
    connection, operation, boundary
):
    client, requests, replies = connection
    page_size = 1 if boundary == "minimum" else operation[5]
    items = [analysis_summary() for _ in range(page_size)]
    replies.append(httpx.Response(200, json={"items": items, "next_page_token": ""}))
    result = await client.call_tool(operation[0], {"page_size": page_size})
    assert not result.is_error
    assert len(result.structured_content["items"]) == page_size
    assert result.structured_content["next_page_token"] == ""
    assert len(requests) == 1


async def test_endpoint_specific_maximum_is_enforced_before_api(connection, operation):
    client, requests, _ = connection
    result = await client.call_tool(
        operation[0], {"page_size": operation[5] + 1}, raise_on_error=False
    )
    assert result.is_error
    assert result.content[0].text == (
        f"page_size doit être inférieur ou égal à {operation[5]}."
    )
    assert requests == []


@pytest.mark.parametrize(
    ("page_size", "message"),
    [
        (555, "page_size doit être inférieur ou égal à 50."),
        (0, "page_size doit être supérieur ou égal à 1."),
        (1.5, "page_size doit être un entier."),
        (True, "page_size doit être un entier."),
        ("555", "page_size doit être un entier."),
    ],
)
async def test_page_size_error_is_actionable_without_pydantic_details(
    connection, page_size, message
):
    client, requests, _ = connection
    result = await client.call_tool(
        "momentum_get_recommendations", {"page_size": page_size}, raise_on_error=False
    )
    assert result.is_error
    assert result.content[0].text == message
    assert requests == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"page_size": 0},
        {"page_size": -1},
        {"page_size": 101},
        {"page_size": 1.5},
        {"page_size": True},
        {"page_token": "x" * 513},
        {"limit": 1},
        {"offset": 0},
    ],
)
async def test_invalid_and_legacy_arguments_never_reach_api(
    connection, operation, arguments
):
    client, requests, _ = connection
    result = await client.call_tool(operation[0], arguments, raise_on_error=False)
    assert result.is_error
    assert requests == []


@pytest.mark.parametrize("failure", [400, 503, "timeout", "invalid_response"])
async def test_upstream_page_errors_never_become_partial_success(
    connection, operation, failure
):
    client, requests, replies = connection
    if failure == "timeout":
        replies.append(httpx.ReadTimeout("private upstream detail"))
    else:
        status = failure if isinstance(failure, int) else 200
        replies.append(httpx.Response(status, text="private upstream detail"))
    result = await client.call_tool(
        operation[0], {"page_token": "rejected-by-api"}, raise_on_error=False
    )
    assert result.is_error
    assert not result.structured_content
    assert "MOMENTUM_API_ERROR" in result.content[0].text
    assert "private upstream detail" not in result.content[0].text
    assert len(requests) == 1


async def test_advertised_tool_schema_exposes_page_contract(connection, operation):
    client, requests, _ = connection
    name, _, _, _, default_size, maximum = operation
    tool = next(tool for tool in await client.list_tools() if tool.name == name)
    properties = tool.input_schema["properties"]
    assert "limit" not in properties and "offset" not in properties
    assert tool.input_schema["additionalProperties"] is False
    assert properties["page_size"]["minimum"] == 1
    assert properties["page_size"]["maximum"] == maximum
    assert properties["page_size"]["default"] == default_size
    assert properties["page_token"]["maxLength"] == 512
    assert properties["page_token"]["default"] == ""
    assert set(tool.output_schema["properties"]) == {"items", "next_page_token"}
    assert set(tool.output_schema["required"]) == {"items", "next_page_token"}
    assert "next_page_token" in tool.description
    assert requests == []


@pytest.mark.parametrize(
    "values", [{"page_size": 0}, {"page_size": 101}, {"page_token": "x" * 513}]
)
def test_domain_rejects_invalid_page_requests(values):
    with pytest.raises(ValueError):
        AnalysisPage(**values)
