import asyncio

import pytest
from pydantic import ValidationError

from app.api.config import create_http_client
from app.config.settings import Settings
from app.lifespan import api_lifespan

API = {"base_url": "https://deepcopy.example.com/v1", "token": "test-token"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"base_url": "http://deepcopy.example.com"},
        {"base_url": "https://user:password@deepcopy.example.com"},
        {"base_url": "https://deepcopy.example.com?token=secret"},
        {"base_url": "https://deepcopy.example.com/#fragment"},
        {"token": ""},
        {"token": "foo\r\nX-Header: bar"},
        {"token": "é"},
        {"read_timeout_seconds": 0},
        {"request_timeout_seconds": float("inf")},
        {"max_connections": 0},
        {"max_response_bytes": 0},
    ],
)
def test_rejects_unsafe_api_config(overrides):
    with pytest.raises(ValidationError):
        Settings(deepcopy_api={**API, **overrides})


def test_nested_environment_and_secret_representation(monkeypatch):
    monkeypatch.setenv("MCP_DEEPCOPY_API__BASE_URL", API["base_url"])
    monkeypatch.setenv("MCP_DEEPCOPY_API__TOKEN", API["token"])
    monkeypatch.setenv("MCP_DEEPCOPY_API__MAX_CONNECTIONS", "3")
    settings = Settings()
    assert settings.deepcopy_api.max_connections == 3
    assert "test-token" not in repr(settings)


@pytest.mark.parametrize(
    "config", [{"base_url": API["base_url"]}, {"token": API["token"]}]
)
def test_partial_configuration_is_an_error(config):
    with pytest.raises(ValidationError):
        Settings(deepcopy_api=config)


def test_production_forbids_even_loopback_http():
    with pytest.raises(ValidationError, match="requires HTTPS"):
        Settings(
            environment="production",
            transport="http",
            auth_mode="jwt",
            jwt_jwks_uri="https://identity.example.com/jwks",
            jwt_issuer="issuer",
            jwt_audience="audience",
            deepcopy_api={**API, "base_url": "http://127.0.0.1:9000"},
        )


async def test_lifespan_closes_client_after_cancellation(monkeypatch):
    settings = Settings(deepcopy_api=API)
    client = create_http_client(settings.deepcopy_api)
    monkeypatch.setattr(
        "app.api.deepcopy.config.client_config.create_http_client",
        lambda config: client,
    )
    with pytest.raises(asyncio.CancelledError):
        async with api_lifespan(settings)(None):
            raise asyncio.CancelledError
    assert client.is_closed
