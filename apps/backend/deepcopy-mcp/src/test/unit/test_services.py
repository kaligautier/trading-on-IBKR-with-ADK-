"""The portfolio service maps API responses to domain models without MCP."""

from app.api.deepcopy.dtos.response.portfolio_responses import (
    AccountsResponse,
    AccountSummaryResponse,
    ContractsResponse,
    PositionsResponse,
    SessionStatusResponse,
)
from app.models.portfolio import Account, AccountSummary, Contract, Position
from app.services.portfolio_service import PortfolioService


class StubClient:
    def __init__(self):
        self.requests = []

    async def get_session(self):
        return SessionStatusResponse(
            authenticated=True,
            established=False,
            competing=False,
            connected=True,
            message="",
        )

    async def list_accounts(self):
        return AccountsResponse.model_validate(
            [
                {
                    "account_id": "U1",
                    "title": None,
                    "display_name": None,
                    "currency": "EUR",
                    "account_type": None,
                }
            ]
        )

    async def get_account_summary(self, request):
        self.requests.append(request)
        return AccountSummaryResponse(
            account_id=request.account_id,
            currency="EUR",
            net_liquidation=10.0,
            total_cash=None,
            buying_power=None,
            available_funds=None,
            gross_position_value=None,
        )

    async def get_positions(self, request):
        self.requests.append(request)
        return PositionsResponse.model_validate(
            [
                {
                    "conid": 1,
                    "symbol": "AAPL",
                    "asset_class": "STK",
                    "quantity": 2.0,
                    "market_price": None,
                    "market_value": None,
                    "average_cost": None,
                    "unrealized_pnl": None,
                    "currency": "USD",
                }
            ]
        )

    async def search_contracts(self, request):
        self.requests.append(request)
        return ContractsResponse.model_validate(
            [
                {
                    "conid": 1,
                    "symbol": None,
                    "company_name": None,
                    "exchange": "NASDAQ",
                    "security_types": ["STK"],
                }
            ]
        )


async def test_maps_responses_to_domain_models():
    stub = StubClient()
    service = PortfolioService(stub)

    assert (await service.get_session()).established is False
    assert await service.list_accounts() == [
        Account(
            account_id="U1",
            title=None,
            display_name=None,
            currency="EUR",
            account_type=None,
        )
    ]
    summary = await service.get_account_summary("U1")
    positions = await service.get_positions("U1", 3)
    contracts = await service.search_contracts("AAPL")

    assert isinstance(summary, AccountSummary) and summary.net_liquidation == 10.0
    assert isinstance(positions[0], Position) and positions[0].quantity == 2.0
    assert isinstance(contracts[0], Contract) and contracts[0].symbol is None
    assert [request.model_dump() for request in stub.requests] == [
        {"account_id": "U1"},
        {"account_id": "U1", "page": 3},
        {"symbol": "AAPL"},
    ]
