"""Unit tests for the IBKR HTTP routes."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.dto.response.ibkr_responses import (
    ContractResponse,
    PositionResponse,
    SessionStatusResponse,
)
from app.routes.ibkr_routes import get_ibkr_portfolio_service
from app.services.ibkr_portfolio_service import IbkrPortfolioService
from app.utils.error import IbkrSessionError, InvalidInputError


@pytest.fixture
def portfolio():
    return MagicMock(spec=IbkrPortfolioService)


@pytest.fixture
def client(portfolio):
    app = create_app()
    app.dependency_overrides[get_ibkr_portfolio_service] = lambda: portfolio
    return TestClient(app)


def position() -> PositionResponse:
    return PositionResponse(
        conid=265598,
        symbol="AAPL",
        asset_class="STK",
        quantity=3,
        market_price=None,
        market_value=None,
        average_cost=None,
        unrealized_pnl=None,
        currency="USD",
    )


class TestIbkrRoutes:
    def should_return_positions(self, client, portfolio):
        portfolio.get_positions.return_value = [position()]

        response = client.get("/ibkr/accounts/U1234567/positions?page=1")

        assert response.status_code == 200
        assert response.json()[0]["symbol"] == "AAPL"
        portfolio.get_positions.assert_called_once_with("U1234567", 1)

    def should_search_contracts(self, client, portfolio):
        portfolio.search_contracts.return_value = [
            ContractResponse(
                conid=265598,
                symbol="AAPL",
                company_name="APPLE INC",
                exchange="NASDAQ",
                security_types=["STK"],
            )
        ]

        response = client.get("/ibkr/contracts", params={"symbol": "AAPL"})

        assert response.status_code == 200
        assert response.json()[0]["exchange"] == "NASDAQ"
        portfolio.search_contracts.assert_called_once_with("AAPL")

    def should_open_the_session(self, client, portfolio):
        portfolio.init_session.return_value = SessionStatusResponse(
            authenticated=True,
            established=True,
            competing=False,
            connected=True,
            message="",
        )

        assert client.post("/ibkr/session/init").json()["established"] is True

    def should_map_a_session_error_to_503(self, client, portfolio):
        portfolio.list_accounts.side_effect = IbkrSessionError("not signed in")

        response = client.get("/ibkr/accounts")

        assert response.status_code == 503
        assert response.json()["error_code"] == "IBKR_SESSION_ERROR"

    def should_map_invalid_input_to_400(self, client, portfolio):
        portfolio.get_summary.side_effect = InvalidInputError("Invalid IBKR account ID")

        assert client.get("/ibkr/accounts/bad/summary").status_code == 400

    def should_reject_a_negative_page(self, client, portfolio):
        assert client.get("/ibkr/accounts/U1/positions?page=-1").status_code == 422
        portfolio.get_positions.assert_not_called()

    def should_expose_no_order_route(self, client):
        paths = client.app.openapi()["paths"]
        ibkr_paths = [path for path in paths if path.startswith("/ibkr")]

        assert len(ibkr_paths) == 6
        assert not [path for path in ibkr_paths if "order" in path or "reply" in path]
