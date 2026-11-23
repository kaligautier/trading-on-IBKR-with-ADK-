"""Read-only IBKR portfolio use cases, independent of FastAPI and ADK."""

import re

from app.clients.ibkr.httpx_ibkr_gateway_client import create_ibkr_gateway_client
from app.clients.ibkr.ibkr_gateway_client import IbkrGatewayClient
from app.dto.response.ibkr_responses import (
    AccountResponse,
    AccountSummaryResponse,
    ContractResponse,
    PositionResponse,
    SessionStatusResponse,
)
from app.mapper import ibkr_mapper
from app.utils.error import InvalidInputError

ACCOUNT_ID_PATTERN = re.compile(r"^[A-Z0-9]{1,20}$")
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,12}$")


class IbkrPortfolioService:
    """Validate inputs, call the gateway client and map its DTOs."""

    def __init__(self, client: IbkrGatewayClient):
        self._client = client

    def session_status(self) -> SessionStatusResponse:
        return ibkr_mapper.to_session_status(self._client.get_auth_status())

    def init_session(self) -> SessionStatusResponse:
        return ibkr_mapper.to_session_status(self._client.init_brokerage_session())

    def list_accounts(self) -> list[AccountResponse]:
        return [ibkr_mapper.to_account(dto) for dto in self._client.list_accounts()]

    def get_summary(self, account_id: str) -> AccountSummaryResponse:
        account_id = _account_id(account_id)
        values = self._client.get_account_summary(account_id)
        return ibkr_mapper.to_account_summary(account_id, values)

    def get_positions(self, account_id: str, page: int = 0) -> list[PositionResponse]:
        if page < 0:
            raise InvalidInputError("page must be zero or positive", {"page": page})
        positions = self._client.get_positions(_account_id(account_id), page)
        return [ibkr_mapper.to_position(dto) for dto in positions]

    def search_contracts(self, symbol: str) -> list[ContractResponse]:
        contracts = self._client.search_contracts(_symbol(symbol))
        return [ibkr_mapper.to_contract(dto) for dto in contracts]


def _account_id(account_id: str) -> str:
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise InvalidInputError("Invalid IBKR account ID", {"field": "account_id"})
    return account_id


def _symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(normalized):
        raise InvalidInputError("Invalid ticker symbol", {"symbol": symbol})
    return normalized


ibkr_portfolio_service = IbkrPortfolioService(create_ibkr_gateway_client())
