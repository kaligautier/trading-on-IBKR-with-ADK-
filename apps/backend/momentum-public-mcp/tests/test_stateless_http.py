"""Native stateless behavior exercised through the real FastMCP HTTP app."""

import json

import pytest
from starlette.testclient import TestClient
from test_server import StaticFingerprint, StubGateway

from momentum_public_mcp.api.errors import MarketScannerApiError, MomentumApiError
from momentum_public_mcp.errors import InstructionError
from momentum_public_mcp.mcp.prompts import public_prompts
from momentum_public_mcp.mcp.prompts.instructions import get_instruction
from momentum_public_mcp.mcp.resources.public_resources import (
    LATEST_MARKET_SCAN_URI,
    MomentumPublicResources,
)
from momentum_public_mcp.mcp.tools.public_tools import MomentumPublicTools
from momentum_public_mcp.protocol import create_http_app
from momentum_public_mcp.server import MomentumPublicMcpServer

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
        headers=headers("tools/call", "list_analyses"),
        json=envelope("tools/call", name="list_analyses", arguments={"limit": 1}),
    )
    assert response.status_code == 200, response.text
    assert "mcp-session-id" not in response.headers
    assert not response.cookies
    result = response.json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"]["result"][0]["ticker"] == "AAPL"


def test_discovery_advertises_modern_protocol(http_client):
    response = http_client.post(
        "/", headers=headers("server/discover"), json=envelope("server/discover")
    )
    assert response.status_code == 200, response.text
    assert VERSION in response.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in response.headers
    capabilities = response.json()["result"]["capabilities"]
    assert {"tools", "resources", "prompts"} <= capabilities.keys()


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
    assert [item["name"] for item in prompts] == ["analyze_ticker"]
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
        headers=headers("prompts/get", "analyze_ticker"),
        json=envelope(
            "prompts/get", name="analyze_ticker", arguments={"ticker": " aapl "}
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
        headers=headers("prompts/get", "analyze_ticker"),
        json=envelope("prompts/get", name="analyze_ticker", arguments=arguments),
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
    assert "latest_analyses" in instruction
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
        method, name = "tools/call", "list_analyses"
        params = {"name": name, "arguments": {}}
        target = "list_analyses"
    elif capability == "resource":
        error = MarketScannerApiError(upstream_status_code=503, details=private)
        method, name = "resources/read", LATEST_MARKET_SCAN_URI
        params = {"uri": name}
        target = "latest_market_scan"
    else:
        error = InstructionError(details=private)
        method, name = "prompts/get", "analyze_ticker"
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
