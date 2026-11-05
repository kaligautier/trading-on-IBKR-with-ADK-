"""External clients preserve wire DTOs and per-API authentication boundaries."""

import httpx
import pytest
from test_gateway import analysis_summary, market_scan

from app.api.market_scanner.config.client_config import (
    create_market_scanner_client,
)
from app.api.momentum.client.momentum_client import MomentumClient
from app.api.momentum.client.signing import SuggestionSigner
from app.api.momentum.config.client_config import create_momentum_client
from app.api.momentum.dtos.request.analyses import AnalysisPageRequest
from app.config.config import Settings


async def test_reader_client_returns_one_page_without_following_the_cursor():
    calls = []

    async def handler(request):
        calls.append(request)
        assert dict(request.url.params) == {
            "ticker": "AAPL",
            "page_size": "10",
            "page_token": "current",
        }
        return httpx.Response(
            200,
            json={"items": [analysis_summary()], "next_page_token": "next"},
        )

    http = httpx.AsyncClient(
        base_url="https://momentum.test", transport=httpx.MockTransport(handler)
    )
    client = MomentumClient(http, SuggestionSigner("test-secret"))
    try:
        response = await client.list_analyses(
            AnalysisPageRequest(ticker="AAPL", page_size=10, page_token="current")
        )
        assert len(calls) == 1
        assert response.next_page_token == "next"
        assert response.items[0].ticker == "AAPL"
    finally:
        await client.close()


@pytest.mark.parametrize("use_iam", [False, True])
async def test_client_factories_keep_urls_and_identity_audiences_separate(
    monkeypatch, use_iam
):
    audiences = []
    requests = []
    transports = []
    original_client = httpx.AsyncClient

    async def handler(request):
        if request.url.host == "metadata.google.internal":
            audience = request.url.params["audience"]
            audiences.append(audience)
            return httpx.Response(200, text=f"id-token:{audience}")
        requests.append(request)
        origin = f"https://{request.url.host}"
        expected = f"Bearer id-token:{origin}" if use_iam else None
        assert request.headers.get("X-Serverless-Authorization") == expected
        if request.url.host == "momentum.test":
            assert request.url.path == "/v1/analyses"
            return httpx.Response(
                200, json={"items": [analysis_summary()], "next_page_token": ""}
            )
        assert request.url == "https://scanner.test/v1/market-scans/latest"
        assert "X-Momentum-Signature" not in request.headers
        return httpx.Response(200, json=market_scan())

    def http_client(**kwargs):
        client = original_client(transport=httpx.MockTransport(handler), **kwargs)
        transports.append(client)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", http_client)
    settings = Settings(
        _env_file=None,
        MOMENTUM_API_URL="https://momentum.test",
        MARKET_SCANNER_API_URL="https://scanner.test",
        MOMENTUM_API_USE_IAM=use_iam,
        SUGGESTION_HASH_SECRET="test-secret",
    )
    momentum = create_momentum_client(settings)
    scanner = create_market_scanner_client(settings, use_iam=use_iam)
    try:
        await momentum.list_analyses(AnalysisPageRequest())
        await scanner.latest_market_scan()
        assert [request.url.host for request in requests] == [
            "momentum.test",
            "scanner.test",
        ]
        expected_audiences = (
            ["https://momentum.test", "https://scanner.test"] if use_iam else []
        )
        assert audiences == expected_audiences
    finally:
        await momentum.close()
        await scanner.close()
    assert all(client.is_closed for client in transports)
