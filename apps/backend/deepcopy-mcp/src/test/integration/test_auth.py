import time

import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from starlette.testclient import TestClient

from app.application import create_server
from app.auth import ExpiringJWTVerifier

ISSUER = "https://identity.example.com/"
AUDIENCE = "deepcopy-mcp"
HEADERS = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-11-25",
}
CALL = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "deepcopy_list_accounts", "arguments": {}},
}


@pytest.fixture
def keys():
    return RSAKeyPair.generate()


@pytest.fixture
def protected_http(api_settings, keys, monkeypatch):
    verifier = ExpiringJWTVerifier(
        public_key=keys.public_key,
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithm="RS256",
        required_scopes=["mcp:access"],
    )
    monkeypatch.setattr("app.application.create_auth", lambda _: verifier)
    app = create_server(api_settings).http_app(
        stateless_http=True,
        json_response=True,
        host_origin_protection=True,
        allowed_hosts=["testserver"],
    )
    with TestClient(app) as client:
        yield client


def token(keys, **overrides):
    values = {"issuer": ISSUER, "audience": AUDIENCE, "scopes": ["mcp:access"]}
    return keys.create_token(**(values | overrides))


def test_authenticates_real_signed_jwt(protected_http, keys):
    response = protected_http.post(
        "/mcp", headers=HEADERS | {"authorization": "Bearer " + token(keys)}, json=CALL
    )
    assert response.status_code == 200
    content = response.json()["result"]["structuredContent"]["result"]
    assert content[0]["account_id"] == "U1234567"


@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "https://wrong.example.com"},
        {"audience": "another-api"},
        {"expires_in_seconds": -60},
        {"scopes": ["unrelated"]},
        {"additional_claims": {"exp": None}},
        {"additional_claims": {"nbf": int(time.time()) + 3600}},
        {"additional_claims": {"nbf": "invalid"}},
        {"additional_claims": {"nbf": True}},
        {"additional_claims": {"nbf": float("inf")}},
    ],
)
def test_rejects_invalid_claims(protected_http, keys, overrides):
    response = protected_http.post(
        "/mcp",
        headers=HEADERS | {"authorization": "Bearer " + token(keys, **overrides)},
        json=CALL,
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("credential", [None, "malformed", "wrong-signature"])
def test_rejects_invalid_credentials(protected_http, credential):
    headers = dict(HEADERS)
    if credential:
        if credential == "wrong-signature":
            credential = token(RSAKeyPair.generate())
        headers["authorization"] = "Bearer " + credential
    response = protected_http.post("/mcp", headers=headers, json=CALL)
    assert response.status_code == 401


def test_health_does_not_expose_configuration(protected_http):
    assert protected_http.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers", [{"host": "evil.example"}, {"origin": "https://evil.example"}]
)
def test_host_origin_protection(protected_http, keys, headers):
    response = protected_http.post(
        "/mcp",
        headers=HEADERS | {"authorization": "Bearer " + token(keys)} | headers,
        json=CALL,
    )
    assert response.status_code in (400, 403, 421)
