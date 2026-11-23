"""Unit tests for the IBKR portfolio service, with an in-memory client."""

import pytest

from app.clients.ibkr.ibkr_gateway_client import IbkrGatewayClient
from app.dto.ibkr.ibkr_dtos import (
    IbkrAccountDto,
    IbkrAuthStatusDto,
    IbkrContractDto,
    IbkrPositionDto,
    IbkrSummaryValueDto,
)
from app.services.ibkr_portfolio_service import IbkrPortfolioService
from app.utils.error import InvalidInputError


class FakeIbkrGatewayClient(IbkrGatewayClient):
    def __init__(self):
        self.calls: list[tuple] = []

    def get_auth_status(self) -> IbkrAuthStatusDto:
        return IbkrAuthStatusDto(authenticated=True)

    def init_brokerage_session(self) -> IbkrAuthStatusDto:
        self.calls.append(("init",))
        return IbkrAuthStatusDto(authenticated=True, established=True)

    def list_accounts(self) -> list[IbkrAccountDto]:
        return [IbkrAccountDto(account_id="U1234567")]

    def get_account_summary(self, account_id: str) -> dict[str, IbkrSummaryValueDto]:
        self.calls.append(("summary", account_id))
        return {"netliquidation": IbkrSummaryValueDto(amount=10.0, currency="EUR")}

    def get_positions(self, account_id: str, page: int) -> list[IbkrPositionDto]:
        self.calls.append(("positions", account_id, page))
        return [IbkrPositionDto(conid=1, ticker="AAPL", position=2)]

    def search_contracts(self, symbol: str) -> list[IbkrContractDto]:
        self.calls.append(("search", symbol))
        return [IbkrContractDto(conid=265598, symbol=symbol)]


@pytest.fixture
def client():
    return FakeIbkrGatewayClient()


@pytest.fixture
def service(client):
    return IbkrPortfolioService(client)


class TestIbkrPortfolioService:
    def should_map_the_session_status(self, service):
        assert service.session_status().authenticated is True

    def should_open_the_session(self, service, client):
        assert service.init_session().established is True
        assert client.calls == [("init",)]

    def should_map_accounts(self, service):
        assert service.list_accounts()[0].account_id == "U1234567"

    def should_map_the_summary(self, service, client):
        summary = service.get_summary("U1234567")

        assert summary.net_liquidation == 10.0
        assert client.calls == [("summary", "U1234567")]

    def should_map_positions(self, service, client):
        positions = service.get_positions("U1234567", page=2)

        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == 2
        assert client.calls == [("positions", "U1234567", 2)]

    def should_normalize_the_searched_symbol(self, service, client):
        assert service.search_contracts(" aapl ")[0].symbol == "AAPL"
        assert client.calls == [("search", "AAPL")]

    @pytest.mark.parametrize("account_id", ["", "u123", "U1/../x", "U" * 21])
    def should_reject_an_invalid_account_id(self, service, client, account_id):
        with pytest.raises(InvalidInputError):
            service.get_summary(account_id)
        assert client.calls == []

    def should_reject_a_negative_page(self, service, client):
        with pytest.raises(InvalidInputError):
            service.get_positions("U1234567", page=-1)
        assert client.calls == []

    @pytest.mark.parametrize("symbol", ["", "AA PL", "A" * 13, "AAPL;DROP"])
    def should_reject_an_invalid_symbol(self, service, client, symbol):
        with pytest.raises(InvalidInputError):
            service.search_contracts(symbol)
        assert client.calls == []

    def should_not_instantiate_an_incomplete_client(self):
        class Incomplete(IbkrGatewayClient):
            pass

        with pytest.raises(TypeError):
            Incomplete()
