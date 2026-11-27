"""Typed HTTP operations for the read-only Deepcopy API /ibkr routes."""

import httpx

from app.api.deepcopy.config.settings import DeepcopyApiSettings
from app.api.deepcopy.dtos.request.account_request import (
    GetAccountRequest,
    GetPositionsRequest,
)
from app.api.deepcopy.dtos.request.search_contracts_request import (
    SearchContractsRequest,
)
from app.api.deepcopy.dtos.response.portfolio_responses import (
    AccountsResponse,
    AccountSummaryResponse,
    ContractsResponse,
    PositionsResponse,
    SessionStatusResponse,
)
from app.api.errors import UpstreamError
from app.api.http import JsonApiClient


class DeepcopyClient:
    def __init__(self, client: httpx.AsyncClient, settings: DeepcopyApiSettings):
        self._http = JsonApiClient(client, settings, "Deepcopy")

    async def get_session(self) -> SessionStatusResponse:
        return await self._http.get("ibkr/session", SessionStatusResponse)

    async def list_accounts(self) -> AccountsResponse:
        return await self._http.get("ibkr/accounts", AccountsResponse)

    async def get_account_summary(
        self, request: GetAccountRequest
    ) -> AccountSummaryResponse:
        response = await self._http.get(
            f"ibkr/accounts/{request.account_id}/summary", AccountSummaryResponse
        )
        if response.account_id != request.account_id:
            raise UpstreamError("Deepcopy API returned a different account")
        return response

    async def get_positions(self, request: GetPositionsRequest) -> PositionsResponse:
        return await self._http.get(
            f"ibkr/accounts/{request.account_id}/positions?page={request.page}",
            PositionsResponse,
        )

    async def search_contracts(
        self, request: SearchContractsRequest
    ) -> ContractsResponse:
        return await self._http.get(
            f"ibkr/contracts?symbol={request.symbol}", ContractsResponse
        )
