"""Use Momentum API's actual cursor encoder and validator at the HTTP boundary."""

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from test_gateway import analysis_summary, gateway_with
from test_server import StaticFingerprint

from app.core_components.resources.public_resources import MomentumPublicResources
from app.core_components.tools.public_tools import MomentumPublicTools
from app.server import MomentumPublicMcpServer


@pytest.fixture(scope="module")
def api_search():
    # Import the provider's real contract, without starting its app or database.
    source = (
        Path(__file__).resolve().parents[2]
        / "momentum-api/src/app/domain/analyses/search.py"
    )
    spec = importlib.util.spec_from_file_location(
        "momentum_api_cursor_contract", source
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules[spec.name]


@pytest.mark.parametrize(
    "tool_name,view,arguments,changed_filter",
    [
        ("momentum_list_analyses", "history", {"ticker": " aapl "}, {"ticker": "MSFT"}),
        (
            "momentum_latest_analyses",
            "latest",
            {"ticker": " aapl ", "rating": " overweight,BUY "},
            {"rating": "Hold"},
        ),
        (
            "momentum_get_recommendations",
            "recommendations",
            {"rating": " overweight,BUY "},
            {"rating": "Hold"},
        ),
    ],
)
async def test_api_generated_cursor_round_trip_and_scope_validation(
    api_search, tool_name, view, arguments, changed_filter
):
    requests = []
    issued = []
    routes = {
        "/v1/analyses": "history",
        "/v1/analyses/latest": "latest",
        "/v1/recommendations": "recommendations",
    }

    def handler(request):
        requests.append(request)
        params = request.url.params
        try:
            query = api_search.AnalysisSearchParams.from_parameters(
                routes[request.url.path],
                params.get("ticker"),
                params.get("rating"),
                int(params["page_size"]),
                params["page_token"],
            )
        except ValueError:
            return httpx.Response(400, json={"detail": "Invalid pagination token"})
        assert query.view == view
        if query.cursor is not None:
            assert query.cursor == issued[0]
            return httpx.Response(200, json={"items": [], "next_page_token": ""})
        item = analysis_summary()
        cursor = api_search.Cursor(
            created_at=item["created_at"], id=item["id"], scope=query.scope
        )
        issued.append(cursor)
        return httpx.Response(
            200, json={"items": [item], "next_page_token": cursor.encode()}
        )

    gateway = gateway_with(handler)
    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway, StaticFingerprint()),
        resources=MomentumPublicResources(gateway),
    ).server
    try:
        async with Client(server) as client:
            first = await client.call_tool(tool_name, arguments)
            token = first.structured_content["next_page_token"]
            assert token == issued[0].encode()
            second = await client.call_tool(
                tool_name, {**arguments, "page_size": 1, "page_token": token}
            )
            assert not second.is_error
            assert second.structured_content == {"items": [], "next_page_token": ""}
            assert len(requests) == 2
            assert requests[1].url.params["page_token"] == token

            rejected = await client.call_tool(
                tool_name,
                {**arguments, **changed_filter, "page_token": token},
                raise_on_error=False,
            )
            assert rejected.is_error
            assert len(requests) == 3

            other_tool = (
                "momentum_latest_analyses"
                if tool_name == "momentum_list_analyses"
                else "momentum_list_analyses"
            )
            rejected = await client.call_tool(
                other_tool, {"page_token": token}, raise_on_error=False
            )
            assert rejected.is_error
            assert len(requests) == 4
    finally:
        await gateway.close()
