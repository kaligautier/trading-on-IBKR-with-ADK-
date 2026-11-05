"""Native stateless behavior exercised through the real FastMCP HTTP app."""

import pytest
from starlette.testclient import TestClient
from test_server import StaticFingerprint, StubGateway

from app.core_components.resources.public_resources import (
    MomentumPublicResources,
)
from app.core_components.tools.public_tools import MomentumPublicTools
from app.protocol import create_http_app
from app.server import MomentumPublicMcpServer

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


def test_discovery_advertises_modern_protocol(http_client):
    response = http_client.post(
        "/", headers=headers("server/discover"), json=envelope("server/discover")
    )
    assert response.status_code == 200, response.text
    assert VERSION in response.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in response.headers
    capabilities = response.json()["result"]["capabilities"]
    assert {"tools", "resources", "prompts"} <= capabilities.keys()


@pytest.mark.parametrize("field", ["protocolVersion", "clientCapabilities"])
def test_each_request_requires_its_own_metadata(http_client, field):
    assert http_client.post("/", headers=headers(), json=envelope()).status_code == 200
    body = envelope()
    del body["params"]["_meta"][PREFIX + field]
    response = http_client.post("/", headers=headers(), json=body)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == -32602


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
