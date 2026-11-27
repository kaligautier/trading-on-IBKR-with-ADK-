"""Adapt the Deepcopy API contract to the domain models, without MCP concerns."""

from app.api.deepcopy.client.deepcopy_client import DeepcopyClient
from app.api.deepcopy.dtos.request.account_request import (
    GetAccountRequest,
    GetPositionsRequest,
)
from app.api.deepcopy.dtos.request.search_contracts_request import (
    SearchContractsRequest,
)
from app.models.identifiers import AccountId, Page, Symbol
from app.models.portfolio import (
    Account,
    AccountSummary,
    Contract,
    Position,
    SessionStatus,
)


class PortfolioService:
    def __init__(self, api: DeepcopyClient):
        self._api = api

    async def get_session(self) -> SessionStatus:
        response = await self._api.get_session()
        return SessionStatus(**response.model_dump())

    async def list_accounts(self) -> list[Account]:
        response = await self._api.list_accounts()
        return [Account(**account.model_dump()) for account in response.root]

    async def get_account_summary(self, account_id: AccountId) -> AccountSummary:
        response = await self._api.get_account_summary(
            GetAccountRequest(account_id=account_id)
        )
        return AccountSummary(**response.model_dump())

    async def get_positions(self, account_id: AccountId, page: Page) -> list[Position]:
        response = await self._api.get_positions(
            GetPositionsRequest(account_id=account_id, page=page)
        )
        return [Position(**position.model_dump()) for position in response.root]

    async def search_contracts(self, symbol: Symbol) -> list[Contract]:
        response = await self._api.search_contracts(
            SearchContractsRequest(symbol=symbol)
        )
        return [Contract(**contract.model_dump()) for contract in response.root]
