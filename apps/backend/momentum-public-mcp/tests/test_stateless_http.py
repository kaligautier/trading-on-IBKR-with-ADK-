"""Native stateless behavior exercised through the real FastMCP HTTP app."""

import json

import pytest
from starlette.testclient import TestClient
from test_server import StaticFingerprint, StubGateway

from app.api.errors import MarketScannerApiError, MomentumApiError
from app.core_components.prompts import public_prompts
from app.core_components.prompts.instructions import get_instruction
from app.core_components.resources.public_resources import (
    LATEST_MARKET_SCAN_URI,
    MomentumPublicResources,
)
from app.core_components.tools.public_tools import MomentumPublicTools
from app.errors import InstructionError
from app.protocol import create_http_app
from app.server import PUBLIC_TOOL_NAMES, MomentumPublicMcpServer

VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"


def envelope(method="tools/list", **params):
    return {
        "jsonrpc": "2.0",
        "id": "independent-request",
        "method": method,
        "params": {
            "_meta": {
                PREFIX + "protocolVersion": VERSION,
                PREFIX + "clientInfo": {"name": "contract-test", "version": "1"},
                PREFIX + "clientCapabilities": {},
            },
            **params,
        },
    }


def headers(method="tools/list", name=None):
    result = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": VERSION,
        "Mcp-Method": method,
    }
    if name:
        result["Mcp-Name"] = name
    return result


@pytest.fixture
def http_client():
    gateway = StubGateway()
    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway, StaticFingerprint()),
        resources=MomentumPublicResources(gateway),
    ).server
    with TestClient(create_http_app(server)) as client:
        yield client


def test_direct_tool_call_needs_no_discovery_or_initialization(http_client):
    response = http_client.post(
        "/",
        headers=headers("tools/call", "momentum_list_analyses"),
        json=envelope(
            "tools/call", name="momentum_list_analyses", arguments={"page_size": 1}
        ),
    )
    assert response.status_code == 200, response.text
    assert "mcp-session-id" not in response.headers
    assert not response.cookies
    result = response.json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"]["items"][0]["ticker"] == "AAPL"


@pytest.mark.parametrize("name", ["list_analyses", "market_scanner_list_analyses"])
def test_tools_require_their_public_namespace(http_client, monkeypatch, name):
    calls = []

    async def unexpected_api(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Unknown public name reached the API")

    monkeypatch.setattr(StubGateway, "list_analyses", unexpected_api)
    response = http_client.post(
        "/",
        headers=headers("tools/call", name),
        json=envelope("tools/call", name=name, arguments={}),
    )
    assert response.json()["result"]["isError"] is True
    assert calls == []


@pytest.mark.parametrize(
    ("method", "params"),
    [
        ("resources/read", {"uri": "momentum://market-scans/latest"}),
        ("prompts/get", {"name": "analyze_ticker", "arguments": {"ticker": "AAPL"}}),
    ],
)
def test_resource_and_prompt_require_their_public_namespace(
    http_client, method, params
):
    response = http_client.post(
        "/",
        headers=headers(method, params.get("name") or params["uri"]),
        json=envelope(method, **params),
    )
    assert "error" in response.json()


def test_discovery_advertises_modern_protocol(http_client):
    response = http_client.post(
        "/", headers=headers("server/discover"), json=envelope("server/discover")
    )
    assert response.status_code == 200, response.text
    assert VERSION in response.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in response.headers
    capabilities = response.json()["result"]["capabilities"]
    assert {"tools", "resources", "prompts"} <= capabilities.keys()


def test_discovery_cursor_paginates_public_tools_without_a_session():
    gateway = StubGateway()
    server = MomentumPublicMcpServer(
        MomentumPublicTools(gateway, StaticFingerprint()),
        resources=MomentumPublicResources(gateway),
        list_page_size=2,
    ).server

    @server.tool(tags={"private"})
    def admin_only() -> str:
        return "not public"

    names = []
    params = {}
    with TestClient(create_http_app(server)) as client:
        for page_number in range(3):
            response = client.post("/", headers=headers(), json=envelope(**params))
            assert response.status_code == 200, response.text
            assert "mcp-session-id" not in response.headers
            assert not response.cookies
            result = response.json()["result"]
            assert len(result["tools"]) == 2
            names.extend(tool["name"] for tool in result["tools"])
            if page_number < 2:
                assert result["nextCursor"]
                params = {"cursor": result["nextCursor"]}
            else:
                assert not result.get("nextCursor")

    assert len(names) == len(set(names))
    assert set(names) == PUBLIC_TOOL_NAMES


def test_resource_and_prompt_are_discoverable(http_client):
    response = http_client.post(
        "/", headers=headers("resources/list"), json=envelope("resources/list")
    )
    assert response.status_code == 200, response.text
    resources = response.json()["result"]["resources"]
    assert [item["uri"] for item in resources] == [LATEST_MARKET_SCAN_URI]
    assert resources[0]["mimeType"] == "application/json"

    response = http_client.post(
        "/", headers=headers("prompts/list"), json=envelope("prompts/list")
    )
    assert response.status_code == 200, response.text
    prompts = response.json()["result"]["prompts"]
    assert [item["name"] for item in prompts] == ["momentum_analyze_ticker"]
    assert prompts[0]["arguments"][0]["name"] == "ticker"
    assert prompts[0]["arguments"][0]["required"] is True


def test_direct_resource_read_needs_no_discovery_or_initialization(http_client):
    response = http_client.post(
        "/",
        headers=headers("resources/read", LATEST_MARKET_SCAN_URI),
        json=envelope("resources/read", uri=LATEST_MARKET_SCAN_URI),
    )
    assert response.status_code == 200, response.text
    assert "mcp-session-id" not in response.headers
    content = response.json()["result"]["contents"][0]
    assert content["mimeType"] == "application/json"
    assert json.loads(content["text"])["report"]["regime"] == "risk-on"


def test_prompt_loads_instructions_with_a_normalized_ticker(http_client, monkeypatch):
    async def unexpected_api_call(*args, **kwargs):
        raise AssertionError("Rendering a prompt must not call an API")

    monkeypatch.setattr(StubGateway, "latest_market_scan", unexpected_api_call)
    monkeypatch.setattr(StubGateway, "latest_analyses", unexpected_api_call)
    response = http_client.post(
        "/",
        headers=headers("prompts/get", "momentum_analyze_ticker"),
        json=envelope(
            "prompts/get",
            name="momentum_analyze_ticker",
            arguments={"ticker": " aapl "},
        ),
    )
    assert response.status_code == 200, response.text
    assert "mcp-session-id" not in response.headers
    message = response.json()["result"]["messages"][0]
    assert message["role"] == "user"
    text = message["content"]["text"]
    assert "ticker=AAPL" in text
    assert LATEST_MARKET_SCAN_URI in text
    assert "{{" not in text


@pytest.mark.parametrize("arguments", [{}, {"ticker": ""}, {"ticker": "{{7*7}}"}])
def test_prompt_rejects_missing_or_invalid_ticker(http_client, arguments):
    response = http_client.post(
        "/",
        headers=headers("prompts/get", "momentum_analyze_ticker"),
        json=envelope(
            "prompts/get", name="momentum_analyze_ticker", arguments=arguments
        ),
    )
    assert "error" in response.json()
    assert "result" not in response.json()


def test_resource_does_not_expose_unexpected_upstream_error(http_client, monkeypatch):
    async def broken_scan(self):
        raise RuntimeError("private upstream detail")

    monkeypatch.setattr(StubGateway, "latest_market_scan", broken_scan)
    response = http_client.post(
        "/",
        headers=headers("resources/read", LATEST_MARKET_SCAN_URI),
        json=envelope("resources/read", uri=LATEST_MARKET_SCAN_URI),
    )
    assert "error" in response.json()
    assert "private upstream detail" not in response.text


def test_instruction_file_loads_without_variables():
    instruction = get_instruction("analyze_ticker")
    assert "momentum_latest_analyses" in instruction
    assert LATEST_MARKET_SCAN_URI in instruction


@pytest.mark.parametrize("field", ["protocolVersion", "clientCapabilities"])
def test_each_request_requires_its_own_metadata(http_client, field):
    assert http_client.post("/", headers=headers(), json=envelope()).status_code == 200
    body = envelope()
    del body["params"]["_meta"][PREFIX + field]
    response = http_client.post("/", headers=headers(), json=body)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == -32602


@pytest.mark.parametrize("method", ["tools/list", "resources/list", "prompts/list"])
def test_client_info_is_optional(http_client, method):
    body = envelope(method)
    del body["params"]["_meta"][PREFIX + "clientInfo"]
    response = http_client.post("/", headers=headers(method), json=body)
    assert response.status_code == 200, response.text
    assert "result" in response.json()
    assert "mcp-session-id" not in response.headers


def test_unsupported_version_has_negotiation_error(http_client):
    body = envelope()
    body["params"]["_meta"][PREFIX + "protocolVersion"] = "2099-01-01"
    response = http_client.post(
        "/", headers={**headers(), "MCP-Protocol-Version": "2099-01-01"}, json=body
    )
    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == -32022
    assert VERSION in error["data"]["supported"]
    assert error["data"]["requested"] == "2099-01-01"


def test_header_body_version_mismatch_is_rejected(http_client):
    body = envelope()
    body["params"]["_meta"][PREFIX + "protocolVersion"] = "2025-11-25"
    response = http_client.post("/", headers=headers(), json=body)
    assert response.status_code == 400


def test_sdk_accepts_headerless_requests_without_session(http_client):
    request_headers = headers()
    del request_headers["MCP-Protocol-Version"]
    response = http_client.post("/", headers=request_headers, json=envelope())
    assert response.status_code == 200, response.text
    assert "tools" in response.json()["result"]
    assert "mcp-session-id" not in response.headers


def test_browser_can_send_stateless_metadata_headers(http_client):
    response = http_client.options(
        "/",
        headers={
            "Origin": "https://deepcopy.fr",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,mcp-protocol-version,mcp-method,mcp-name"
            ),
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    response = http_client.post(
        "/", headers={**headers(), "Origin": "https://deepcopy.fr"}, json=envelope()
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


@pytest.mark.parametrize(
    "method", ["initialize", "ping", "logging/setLevel", "unknown/method"]
)
def test_removed_and_unknown_methods_are_not_available_in_modern_protocol(
    http_client, method
):
    response = http_client.post("/", headers=headers(method), json=envelope(method))
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == -32601


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_no_standalone_stream_or_session_delete(http_client, method):
    response = http_client.request(method, "/", headers=headers())
    assert response.status_code == 405, response.text


def test_repeated_request_id_is_independent_across_server_instances():
    for _ in range(2):
        gateway = StubGateway()
        server = MomentumPublicMcpServer(
            MomentumPublicTools(gateway, StaticFingerprint()),
            resources=MomentumPublicResources(gateway),
        ).server
        with TestClient(create_http_app(server)) as client:
            response = client.post("/", headers=headers(), json=envelope())
            assert response.status_code == 200, response.text
            assert "mcp-session-id" not in response.headers


@pytest.mark.parametrize(
    "version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
)
def test_sdk_legacy_initialization_keeps_transport_sessionless(http_client, version):
    body = envelope(
        "initialize",
        protocolVersion=version,
        capabilities={},
        clientInfo={"name": "legacy", "version": "1"},
    )
    body["params"]["_meta"][PREFIX + "protocolVersion"] = version
    response = http_client.post(
        "/",
        headers={**headers("initialize"), "MCP-Protocol-Version": version},
        json=body,
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["protocolVersion"] == version
    assert "mcp-session-id" not in response.headers


@pytest.mark.parametrize("capability", ["tool", "resource", "prompt"])
def test_application_errors_use_native_mcp_errors_without_private_details(
    http_client, monkeypatch, capability
):
    private = {"internal": "private-error-context"}
    if capability == "tool":
        error = MomentumApiError(upstream_status_code=503, details=private)
        method, name = "tools/call", "momentum_list_analyses"
        params = {"name": name, "arguments": {}}
        target = "list_analyses"
    elif capability == "resource":
        error = MarketScannerApiError(upstream_status_code=503, details=private)
        method, name = "resources/read", LATEST_MARKET_SCAN_URI
        params = {"uri": name}
        target = "latest_market_scan"
    else:
        error = InstructionError(details=private)
        method, name = "prompts/get", "momentum_analyze_ticker"
        params = {"name": name, "arguments": {"ticker": "AAPL"}}

    async def failed_api(*args, **kwargs):
        raise error

    def failed_instruction(*args, **kwargs):
        raise error

    if capability == "prompt":
        monkeypatch.setattr(public_prompts, "get_instruction", failed_instruction)
    else:
        monkeypatch.setattr(StubGateway, target, failed_api)
    response = http_client.post(
        "/", headers=headers(method, name), json=envelope(method, **params)
    )
    body = response.json()
    if capability == "tool":
        assert response.status_code == 200
        assert body["result"]["isError"] is True
    else:
        assert "error" in body
        assert "result" not in body
    assert error.error_code.value in response.text
    assert error.message in response.text
    assert "private-error-context" not in response.text
    assert "upstream_status_code" not in response.text


@pytest.mark.parametrize("failure", [ValueError, RuntimeError, TypeError])
@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("momentum_list_analyses", {}),
        ("momentum_latest_analyses", {}),
        ("momentum_get_recommendations", {}),
        (
            "momentum_get_analysis",
            {"analysis_id": "11111111-1111-1111-1111-111111111111"},
        ),
        ("momentum_suggest_ticker", {"symbol": "MSFT"}),
        (
            "momentum_get_suggestion_status",
            {"suggestion_id": "22222222-2222-2222-2222-222222222222"},
        ),
    ],
)
def test_unexpected_tool_failures_stay_masked(
    http_client, monkeypatch, failure, name, arguments
):
    async def failed_operation(*args, **kwargs):
        raise failure("private upstream SQL, credential or diagnostic")

    monkeypatch.setattr(StubGateway, name.removeprefix("momentum_"), failed_operation)
    response = http_client.post(
        "/",
        headers=headers("tools/call", name),
        json=envelope("tools/call", name=name, arguments=arguments),
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == f"Error calling tool '{name}'"
    assert "private upstream" not in response.text


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("momentum_list_analyses", {"ticker": "../AAPL"}, "Ticker must contain"),
        ("momentum_latest_analyses", {"rating": "unknown"}, "Allowed ratings:"),
        ("momentum_get_recommendations", {"rating": "unknown"}, "Allowed ratings:"),
        (
            "momentum_get_analysis",
            {"analysis_id": "bad"},
            "Analysis id must be a valid UUID.",
        ),
        (
            "momentum_suggest_ticker",
            {"symbol": "MSFT", "reason": "x" * 501},
            "Suggestion reason must contain at most 500 characters.",
        ),
        (
            "momentum_get_suggestion_status",
            {"suggestion_id": "bad"},
            "Suggestion id must be a valid UUID.",
        ),
    ],
)
def test_expected_input_errors_are_public_without_calling_api(
    http_client, monkeypatch, name, arguments, message
):
    calls = []

    async def unexpected_api(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Invalid input reached the API")

    monkeypatch.setattr(StubGateway, name.removeprefix("momentum_"), unexpected_api)
    response = http_client.post(
        "/",
        headers=headers("tools/call", name),
        json=envelope("tools/call", name=name, arguments=arguments),
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert message in result["content"][0]["text"]
    assert calls == []


@pytest.mark.parametrize(
    ("version", "is_error"), [("1", False), ("0.1.0", True), ("2", True)]
)
def test_http_tool_version_routes_exactly_without_falling_back(
    http_client, monkeypatch, version, is_error
):
    calls = []
    original = StubGateway.list_analyses

    async def traced_operation(*args, **kwargs):
        calls.append(True)
        return await original(*args, **kwargs)

    monkeypatch.setattr(StubGateway, "list_analyses", traced_operation)
    body = envelope("tools/call", name="momentum_list_analyses", arguments={})
    body["params"]["_meta"]["fastmcp"] = {"version": version}
    response = http_client.post(
        "/", headers=headers("tools/call", "momentum_list_analyses"), json=body
    )
    assert response.status_code == 200
    assert response.json()["result"].get("isError", False) is is_error
    assert calls == ([] if is_error else [True])
