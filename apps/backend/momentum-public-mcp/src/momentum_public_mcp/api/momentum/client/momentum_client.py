"""Typed HTTP operations for the external Momentum API."""

from uuid import UUID

import httpx

from momentum_public_mcp.api.auth import CloudRunIdentityHeaders
from momentum_public_mcp.api.errors import MomentumApiError
from momentum_public_mcp.api.http import ApiHttpClient
from momentum_public_mcp.api.momentum.client.signing import SuggestionSigner
from momentum_public_mcp.api.momentum.dtos.request.analyses import AnalysisPageRequest
from momentum_public_mcp.api.momentum.dtos.request.suggestions import SuggestionRequest
from momentum_public_mcp.api.momentum.dtos.response.analyses import (
    AnalysisDetail,
    ReaderPage,
)
from momentum_public_mcp.api.momentum.dtos.response.suggestions import Suggestion


class MomentumClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        signer: SuggestionSigner,
        identity_headers: CloudRunIdentityHeaders | None = None,
    ):
        self._http = ApiHttpClient(
            client, identity_headers, error_type=MomentumApiError
        )
        self._signer = signer

    async def close(self) -> None:
        await self._http.close()

    async def list_analyses(self, request: AnalysisPageRequest) -> ReaderPage:
        return await self._get_page("/v1/analyses", request)

    async def latest_analyses(self, request: AnalysisPageRequest) -> ReaderPage:
        return await self._get_page("/v1/analyses/latest", request)

    async def get_recommendations(self, request: AnalysisPageRequest) -> ReaderPage:
        return await self._get_page("/v1/recommendations", request)

    async def _get_page(self, path: str, request: AnalysisPageRequest) -> ReaderPage:
        response = await self._http.request(
            "GET", path, params=request.model_dump(exclude_none=True)
        )
        return self._http.model(response, ReaderPage)

    async def get_analysis(self, analysis_id: UUID) -> AnalysisDetail:
        response = await self._http.request("GET", f"/v1/analyses/{analysis_id}")
        return self._http.model(response, AnalysisDetail)

    async def suggest_ticker(
        self, request: SuggestionRequest, caller_fingerprint: str
    ) -> Suggestion:
        try:
            response = await self._http.request(
                "POST",
                "/suggestions",
                json=request.model_dump(mode="json"),
                headers=self._signer.headers(caller_fingerprint),
            )
        except MomentumApiError as error:
            if error.upstream_status_code == 409:
                raise MomentumApiError(
                    "This ticker already has a current analysis in Momentum.",
                    upstream_status_code=409,
                ) from error
            raise
        return self._http.model(response, Suggestion)

    async def get_suggestion_status(self, suggestion_id: UUID) -> Suggestion:
        response = await self._http.request("GET", f"/suggestions/{suggestion_id}")
        return self._http.model(response, Suggestion)
