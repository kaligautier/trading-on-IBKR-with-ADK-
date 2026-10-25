"""Local API credentials stay isolated from each other and Cloud Run IAM."""

import httpx
import pytest

from momentum_public_mcp.application import MomentumPublicApplication
from momentum_public_mcp.config import Settings


@pytest.mark.parametrize("iam", [False, True])
async def test_backend_credentials_are_isolated(monkeypatch, iam):
    monkeypatch.setenv("SUGGESTION_HASH_SECRET", "disposable-signing-key")
    monkeypatch.setenv("MOMENTUM_API_URL", "https://momentum.test")
    monkeypatch.setenv("MARKET_SCANNER_API_URL", "https://scanner.test")
    monkeypatch.setenv("MOMENTUM_API_TOKEN", "disposable-momentum-token")
    monkeypatch.setenv("MARKET_SCANNER_API_TOKEN", "disposable-scanner-token")
    monkeypatch.setenv("MOMENTUM_API_USE_IAM", str(iam))
    settings = Settings(_env_file=None)
    assert "disposable-momentum-token" not in repr(settings)
    assert "disposable-scanner-token" not in repr(settings)

    clients = []
    original = httpx.AsyncClient

    def capture_client(**kwargs):
        client = original(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", capture_client)
    application = MomentumPublicApplication(settings)
    try:
        requests = [client.build_request("GET", "/v1/check") for client in clients]
        assert [request.url.host for request in requests] == [
            "momentum.test",
            "scanner.test",
        ]
        expected = (
            [None, None]
            if iam
            else [
                "Bearer disposable-momentum-token",
                "Bearer disposable-scanner-token",
            ]
        )
        assert [
            request.headers.get("authorization") for request in requests
        ] == expected
    finally:
        await application._gateway.close()
