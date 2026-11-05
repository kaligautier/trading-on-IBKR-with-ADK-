"""Typed HTTP operations for the external Momentum API."""

from uuid import UUID

import httpx

from app.api.auth import CloudRunIdentityHeaders
from app.api.errors import MomentumApiError
from app.api.http import ApiHttpClient
from app.api.momentum.client.signing import SuggestionSigner
from app.api.momentum.config.constants import (
    MOMENTUM_ANALYSIS_API_PREFIX,
)
from app.api.momentum.dtos.request.analyses import AnalysisPageRequest
from app.api.momentum.dtos.request.suggestions import SuggestionRequest
from app.api.momentum.dtos.response.analyses import (
    AnalysisDetail,
    ReaderPage,
)
from app.api.momentum.dtos.response.suggestions import Suggestion


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
        return await self._get_page(f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses", request)

    async def latest_analyses(self, request: AnalysisPageRequest) -> ReaderPage:
        return await self._get_page(
            f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses/latest", request
        )

    async def get_recommendations(self, request: AnalysisPageRequest) -> ReaderPage:
        return await self._get_page(
            f"{MOMENTUM_ANALYSIS_API_PREFIX}/recommendations", request
        )

    async def _get_page(self, path: str, request: AnalysisPageRequest) -> ReaderPage:
        response = await self._http.request(
            "GET", path, params=request.model_dump(exclude_none=True)
        )
        return self._http.model(response, ReaderPage)

    async def get_analysis(self, analysis_id: UUID) -> AnalysisDetail:
        response = await self._http.request(
            "GET", f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses/{analysis_id}"
        )
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
