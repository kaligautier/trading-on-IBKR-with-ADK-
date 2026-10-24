"""Contract tests for the public Momentum HTTP gateway."""

import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from uuid import UUID

import httpx
import pytest

from momentum_public_mcp.domain import (
    AnalysisId,
    AnalysisPage,
    Ratings,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)
from momentum_public_mcp.gateway import (
    CloudRunIdentityHeaders,
    MetadataIdentityTokenProvider,
    MomentumApiError,
    MomentumHttpGateway,
    SuggestionSigner,
)

ANALYSIS_ID = UUID("11111111-1111-1111-1111-111111111111")
SUGGESTION_ID = UUID("22222222-2222-2222-2222-222222222222")


class StaticIdentityTokenProvider:
    async def token(self) -> str:
        return "cloud-run-id-token"


def analysis_summary() -> dict:
    return {
        "id": str(ANALYSIS_ID),
        "ticker": "AAPL",
        "analysis_date": str(date(2026, 8, 1)),
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
        "llm_provider": "google",
        "next_analysis_date": None,
    }


def suggestion() -> dict:
    return {
        "id": str(SUGGESTION_ID),
        "symbol": "MSFT",
        "reason": "Strong fundamentals",
        "status": "pending",
        "suggested_by": "pseudonym",
        "source": "mcp",
        "created_at": datetime(2026, 8, 2, tzinfo=timezone.utc).isoformat(),
        "reviewed_at": None,
        "reviewed_by": None,
        "review_reason": None,
    }


def market_scan() -> dict:
    return {
        "id": "33333333-3333-3333-3333-333333333333",
        "scan_date": "2026-08-06",
        "report": {"schema_version": 3, "regime": "risk-on", "assets": []},
        "created_at": "2026-08-06T10:00:00Z",
    }


async def test_list_analyses_calls_only_the_public_route() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/analyses"
        assert dict(request.url.params) == {
            "ticker": "AAPL",
            "page_size": "20",
            "page_token": "",
        }
        return httpx.Response(
            200, json={"items": [analysis_summary()], "next_page_token": ""}
        )

    gateway = gateway_with(handler)

    analyses = await gateway.list_analyses(
        TickerSymbol("aapl"),
        AnalysisPage(limit=20, offset=0),
    )

    assert analyses.items[0].ticker == "AAPL"


async def test_momentum_requests_include_cloud_run_identity_when_enabled() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Serverless-Authorization"] == (
            "Bearer cloud-run-id-token"
        )
        return httpx.Response(
            200, json={"items": [analysis_summary()], "next_page_token": ""}
        )

    identity_headers = CloudRunIdentityHeaders(StaticIdentityTokenProvider())
    gateway = gateway_with(handler, identity_headers=identity_headers)

    result = await gateway.latest_analyses(None, None)

    assert result.items[0].ticker == "AAPL"


async def test_metadata_identity_token_uses_momentum_api_as_audience() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Metadata-Flavor"] == "Google"
        assert request.url.params["audience"] == "https://momentum.test"
        return httpx.Response(200, text="signed-id-token")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MetadataIdentityTokenProvider(client, "https://momentum.test")

    assert await provider.token() == "signed-id-token"


async def test_recommendations_send_normalized_ratings() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/recommendations"
        assert dict(request.url.params) == {
            "rating": "Buy,Overweight",
            "page_size": "10",
            "page_token": "",
        }
        return httpx.Response(
            200, json={"items": [analysis_summary()], "next_page_token": ""}
        )

    gateway = gateway_with(handler)

    analyses = await gateway.get_recommendations(
        Ratings.from_csv(" buy, OVERWEIGHT "),
        10,
    )

    assert len(analyses.items) == 1


async def test_latest_market_scan_uses_scanner_consultation_api() -> None:
    async def momentum_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected request to Momentum API: {request.url}")

    async def scanner_handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://scanner.test/market-scans/latest"
        return httpx.Response(200, json=market_scan())

    momentum_client = httpx.AsyncClient(
        transport=httpx.MockTransport(momentum_handler),
        base_url="https://momentum.test",
    )
    scanner_client = httpx.AsyncClient(
        transport=httpx.MockTransport(scanner_handler),
        base_url="https://scanner.test",
    )
    gateway = MomentumHttpGateway(
        momentum_client,
        SuggestionSigner("test-secret"),
        scanner_client,
    )

    result = await gateway.latest_market_scan()

    assert result.report["regime"] == "risk-on"
    await gateway.close()


def test_ratings_reject_values_outside_the_public_vocabulary() -> None:
    with pytest.raises(ValueError, match="Allowed ratings"):
        Ratings.from_csv("Buy,ExecuteAdminTask")


async def test_suggestion_keeps_signature_with_cloud_run_identity() -> None:
    secret = "test-secret"
    caller_fingerprint = "caller-fingerprint"

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/suggestions"
        assert payload == {"symbol": "MSFT", "reason": "Strong fundamentals"}
        assert request.headers["X-Momentum-Caller"] == caller_fingerprint
        assert request.headers["X-Serverless-Authorization"] == (
            "Bearer cloud-run-id-token"
        )
        expected_signature = hmac.new(
            secret.encode(),
            caller_fingerprint.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert request.headers["X-Momentum-Signature"] == expected_signature
        return httpx.Response(202, json=suggestion())

    identity_headers = CloudRunIdentityHeaders(StaticIdentityTokenProvider())
    gateway = gateway_with(handler, secret, identity_headers)

    result = await gateway.suggest_ticker(
        TickerSymbol("msft"),
        SuggestionReason("Strong fundamentals"),
        caller_fingerprint,
    )

    assert result.status == "pending"


async def test_not_found_is_a_sanitized_gateway_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/v1/analyses/{ANALYSIS_ID}"
        return httpx.Response(404, text="database row and stack trace")

    gateway = gateway_with(handler)

    with pytest.raises(MomentumApiError, match="not found") as captured:
        await gateway.get_analysis(AnalysisId(ANALYSIS_ID))

    assert "database" not in str(captured.value)


async def test_current_analysis_conflict_is_explained_to_mcp_user() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/suggestions"
        return httpx.Response(
            409,
            json={"detail": "NVDA already has a current Momentum analysis."},
        )

    gateway = gateway_with(handler)

    with pytest.raises(MomentumApiError, match="current analysis"):
        await gateway.suggest_ticker(
            TickerSymbol("NVDA"),
            SuggestionReason("Réanalyse"),
            "caller-fingerprint",
        )


async def test_suggestion_status_uses_the_public_status_route() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/suggestions/{SUGGESTION_ID}"
        return httpx.Response(200, json=suggestion())

    gateway = gateway_with(handler)

    result = await gateway.get_suggestion_status(SuggestionId(SUGGESTION_ID))

    assert result.id == SUGGESTION_ID


def gateway_with(
    handler,
    secret: str = "test-secret",
    identity_headers=None,
) -> MomentumHttpGateway:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://momentum.test")
    return MomentumHttpGateway(
        client,
        SuggestionSigner(secret),
        identity_headers=identity_headers,
    )


async def test_original_offset_window_traverses_reader_cursors():
    calls = []

    async def handler(request):
        calls.append(dict(request.url.params))
        if not request.url.params["page_token"]:
            return httpx.Response(
                200, json={"items": [analysis_summary()], "next_page_token": "page2"}
            )
        return httpx.Response(
            200,
            json={
                "items": [{**analysis_summary(), "ticker": "MSFT"}],
                "next_page_token": "page3",
            },
        )

    gateway = gateway_with(handler)
    result = await gateway.list_analyses(None, AnalysisPage(limit=1, offset=1))
    assert [item.ticker for item in result.items] == ["MSFT"]
    assert calls == [
        {"page_size": "2", "page_token": ""},
        {"page_size": "1", "page_token": "page2"},
    ]
    await gateway.close()


async def test_latest_does_not_drop_reader_pages():
    async def handler(request):
        first = not request.url.params["page_token"]
        return httpx.Response(
            200,
            json={
                "items": [
                    {**analysis_summary(), "ticker": "AAPL" if first else "MSFT"}
                ],
                "next_page_token": "page2" if first else "",
            },
        )

    gateway = gateway_with(handler)
    result = await gateway.latest_analyses(None, None)
    assert [item.ticker for item in result.items] == ["AAPL", "MSFT"]
    await gateway.close()


async def test_repeated_cursor_fails_instead_of_looping():
    async def handler(request):
        return httpx.Response(200, json={"items": [], "next_page_token": "same"})

    gateway = gateway_with(handler)
    with pytest.raises(MomentumApiError, match="repeated cursor"):
        await gateway.latest_analyses(None, None)
    await gateway.close()


async def test_scanner_uses_its_own_identity_headers():
    class ScannerIdentity:
        async def token(self):
            return "scanner-audience-token"

    async def handler(request):
        assert (
            request.headers["X-Serverless-Authorization"]
            == "Bearer scanner-audience-token"
        )
        return httpx.Response(200, json=market_scan())

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://scanner.test"
    )
    gateway = MomentumHttpGateway(
        client,
        SuggestionSigner("test-secret"),
        identity_headers=CloudRunIdentityHeaders(StaticIdentityTokenProvider()),
        scanner_identity_headers=CloudRunIdentityHeaders(ScannerIdentity()),
    )
    await gateway.latest_market_scan()
    await gateway.close()


async def test_missing_momentum_suggestions_route_is_a_sanitized_error():
    async def handler(request):
        assert request.url == "https://momentum.test/suggestions"
        return httpx.Response(404, text="private upstream details")

    gateway = gateway_with(handler)
    with pytest.raises(MomentumApiError, match="not found") as captured:
        await gateway.suggest_ticker(
            TickerSymbol("MSFT"), SuggestionReason(""), "caller"
        )
    assert "private upstream" not in str(captured.value)
    await gateway.close()
