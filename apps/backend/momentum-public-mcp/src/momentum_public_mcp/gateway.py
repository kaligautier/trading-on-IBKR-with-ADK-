"""Validated HTTP adapter for the public Momentum API."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from momentum_public_mcp.domain import (
    AnalysisDetail,
    AnalysisId,
    AnalysisPage,
    AnalysisSummaries,
    AnalysisSummary,
    MarketScan,
    Ratings,
    Suggestion,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)

logger = logging.getLogger(__name__)


class MomentumApiError(RuntimeError):
    """Sanitized public API failure."""


class ReaderPage(BaseModel):
    items: list[AnalysisSummary]
    next_page_token: str


class IdentityTokenProvider(Protocol):
    async def token(self) -> str | None: ...


class DisabledIdentityTokenProvider:
    async def token(self) -> str | None:
        return None


class MetadataIdentityTokenProvider:
    """Obtain a Google-signed ID token for the private Momentum API."""

    _ENDPOINT = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity"
    )

    def __init__(self, client: httpx.AsyncClient, audience: str):
        self._client = client
        self._audience = audience

    async def token(self) -> str:
        try:
            response = await self._client.get(
                self._ENDPOINT,
                params={"audience": self._audience, "format": "full"},
                headers={"Metadata-Flavor": "Google"},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise MomentumApiError(
                "Cloud Run service identity is unavailable."
            ) from error
        token = response.text.strip()
        if token:
            return token
        raise MomentumApiError("Cloud Run service identity is unavailable.")


class CloudRunIdentityHeaders:
    """Build the Cloud Run edge-authentication header for API requests."""

    def __init__(self, token_provider: IdentityTokenProvider):
        self._token_provider = token_provider

    async def values(self) -> dict[str, str]:
        token = await self._token_provider.token()
        if token is None:
            return {}
        return {"X-Serverless-Authorization": f"Bearer {token}"}


class MomentumPublicGateway(Protocol):
    async def latest_market_scan(self) -> MarketScan: ...
    async def list_analyses(
        self, ticker: TickerSymbol | None, page: AnalysisPage
    ) -> AnalysisSummaries: ...

    async def latest_analyses(
        self, ticker: TickerSymbol | None, ratings: Ratings | None
    ) -> AnalysisSummaries: ...

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail: ...

    async def get_recommendations(
        self, ratings: Ratings, limit: int
    ) -> AnalysisSummaries: ...

    async def suggest_ticker(
        self,
        symbol: TickerSymbol,
        reason: SuggestionReason,
        caller_fingerprint: str,
    ) -> Suggestion: ...

    async def get_suggestion_status(
        self, suggestion_id: SuggestionId
    ) -> Suggestion: ...


class SuggestionSigner:
    """Authenticate a pseudonymous caller assertion to Momentum API."""

    def __init__(self, secret: str):
        if not secret:
            raise ValueError("Suggestion hash secret is required.")
        self._secret = secret.encode()

    def headers(self, caller_fingerprint: str) -> dict[str, str]:
        signature = hmac.new(
            self._secret,
            caller_fingerprint.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Momentum-Caller": caller_fingerprint,
            "X-Momentum-Signature": signature,
        }


class MomentumHttpGateway:
    """Call only allow-listed public Momentum endpoints."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        signer: SuggestionSigner,
        market_scanner_client: httpx.AsyncClient | None = None,
        identity_headers: CloudRunIdentityHeaders | None = None,
        scanner_identity_headers: CloudRunIdentityHeaders | None = None,
    ):
        self._client = client
        self._market_scanner_client = market_scanner_client or client
        self._signer = signer
        self._identity_headers = identity_headers or CloudRunIdentityHeaders(
            DisabledIdentityTokenProvider()
        )
        self._scanner_identity_headers = (
            scanner_identity_headers
            or CloudRunIdentityHeaders(DisabledIdentityTokenProvider())
        )

    async def list_analyses(
        self,
        ticker: TickerSymbol | None,
        page: AnalysisPage,
    ) -> AnalysisSummaries:
        parameters = {}
        if ticker is not None:
            parameters["ticker"] = ticker.value
        return await self._pages("/v1/analyses", parameters, page.limit, page.offset)

    async def latest_market_scan(self) -> MarketScan:
        response = await self._market_scanner_request("GET", "/market-scans/latest")
        return self._model(response, MarketScan)

    async def latest_analyses(
        self,
        ticker: TickerSymbol | None,
        ratings: Ratings | None,
    ) -> AnalysisSummaries:
        parameters = self._latest_parameters(ticker, ratings)
        return await self._pages("/v1/analyses/latest", parameters)

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail:
        response = await self._request("GET", f"/v1/analyses/{analysis_id.value}")
        return self._model(response, AnalysisDetail)

    async def get_recommendations(
        self,
        ratings: Ratings,
        limit: int,
    ) -> AnalysisSummaries:
        return await self._pages(
            "/v1/recommendations", {"rating": ratings.as_csv()}, limit
        )

    async def _pages(
        self, path: str, parameters: dict, limit: int | None = None, offset: int = 0
    ) -> AnalysisSummaries:
        """Translate the original MCP window into the reader's cursor protocol.

        Never return a silently truncated latest-per-ticker result. The enclosing
        tool deadline bounds traversal; repeated cursors are an upstream error.
        """
        items: list[AnalysisSummary] = []
        token = ""
        seen: set[str] = set()
        while True:
            size = 100 if limit is None else min(100, offset + limit - len(items))
            response = await self._request(
                "GET",
                path,
                params={**parameters, "page_size": size, "page_token": token},
            )
            page = self._model(response, ReaderPage)
            skipped = min(offset, len(page.items))
            offset -= skipped
            items.extend(page.items[skipped:])
            if not page.next_page_token or (limit is not None and len(items) >= limit):
                return AnalysisSummaries(tuple(items))
            token = page.next_page_token
            if token in seen:
                raise MomentumApiError(
                    "Momentum public API returned a repeated cursor."
                )
            seen.add(token)

    async def suggest_ticker(
        self,
        symbol: TickerSymbol,
        reason: SuggestionReason,
        caller_fingerprint: str,
    ) -> Suggestion:
        payload = {"symbol": symbol.value, "reason": reason.value}
        headers = self._signer.headers(caller_fingerprint)
        response = await self._request(
            "POST", "/suggestions", json=payload, headers=headers
        )
        return self._model(response, Suggestion)

    async def get_suggestion_status(self, suggestion_id: SuggestionId) -> Suggestion:
        response = await self._request("GET", f"/suggestions/{suggestion_id.value}")
        return self._model(response, Suggestion)

    async def close(self) -> None:
        await self._client.aclose()
        if self._market_scanner_client is not self._client:
            await self._market_scanner_client.aclose()

    async def _request(self, method: str, path: str, **arguments) -> httpx.Response:
        authenticated_arguments = await self._authenticated(arguments)
        return await self._request_from(
            self._client,
            method,
            path,
            **authenticated_arguments,
        )

    async def _authenticated(self, arguments: dict) -> dict:
        headers = dict(arguments.get("headers", {}))
        headers.update(await self._identity_headers.values())
        return {**arguments, "headers": headers}

    async def _market_scanner_request(
        self, method: str, path: str, **arguments
    ) -> httpx.Response:
        headers = dict(arguments.pop("headers", {}))
        headers.update(await self._scanner_identity_headers.values())
        return await self._request_from(
            self._market_scanner_client, method, path, headers=headers, **arguments
        )

    async def _request_from(
        self, client: httpx.AsyncClient, method: str, path: str, **arguments
    ) -> httpx.Response:
        try:
            response = await client.request(method, path, **arguments)
        except httpx.HTTPError as error:
            logger.warning("Reader transport failure: %s", type(error).__name__)
            raise MomentumApiError("Momentum public API is unavailable.") from error
        self._ensure_success(response)
        return response

    @staticmethod
    def _ensure_success(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise MomentumApiError("Momentum public resource not found.")
        if response.status_code == 429:
            raise MomentumApiError("Momentum public request limit reached.")
        if response.status_code == 409:
            raise MomentumApiError(
                "This ticker already has a current analysis in Momentum."
            )
        if response.status_code == 422:
            raise MomentumApiError("Momentum rejected the public input.")
        if response.is_error:
            raise MomentumApiError("Momentum public API request failed.")

    @staticmethod
    def _model(response: httpx.Response, model_type):
        try:
            return model_type.model_validate_json(response.content)
        except ValidationError as error:
            message = "Momentum public API returned invalid data."
            raise MomentumApiError(message) from error

    @staticmethod
    def _latest_parameters(
        ticker: TickerSymbol | None,
        ratings: Ratings | None,
    ) -> dict[str, str]:
        parameters: dict[str, str] = {}
        if ticker is not None:
            parameters["ticker"] = ticker.value
        if ratings is not None:
            parameters["rating"] = ratings.as_csv()
        return parameters
