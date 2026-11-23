"""Unit tests for the IBKR HTTP routes."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.routes.ibkr_routes import get_ibkr_gateway
from app.services.ibkr_gateway_service import IbkrGatewayService
from app.utils.error import IbkrSessionError, InvalidInputError


@pytest.fixture
def gateway():
    return MagicMock(spec=IbkrGatewayService)


@pytest.fixture
def client(gateway):
    app = create_app()
    app.dependency_overrides[get_ibkr_gateway] = lambda: gateway
    return TestClient(app)


class TestIbkrRoutes:
    def should_return_positions(self, client, gateway):
        gateway.get_positions.return_value = [{"conid": 265598}]

        response = client.get("/ibkr/accounts/U1234567/positions?page=1")

        assert response.status_code == 200
        assert response.json() == [{"conid": 265598}]
        gateway.get_positions.assert_called_once_with("U1234567", 1)

    def should_search_contracts(self, client, gateway):
        gateway.search_contracts.return_value = [{"conid": "265598"}]

        response = client.get("/ibkr/contracts", params={"symbol": "AAPL"})

        assert response.status_code == 200
        gateway.search_contracts.assert_called_once_with("AAPL")

    def should_open_the_session(self, client, gateway):
        gateway.init_session.return_value = {"authenticated": True}

        assert client.post("/ibkr/session/init").status_code == 200

    def should_map_a_session_error_to_503(self, client, gateway):
        gateway.list_accounts.side_effect = IbkrSessionError("not signed in")

        response = client.get("/ibkr/accounts")

        assert response.status_code == 503
        assert response.json()["error_code"] == "IBKR_SESSION_ERROR"

    def should_map_invalid_input_to_400(self, client, gateway):
        gateway.get_summary.side_effect = InvalidInputError("Invalid IBKR account ID")

        assert client.get("/ibkr/accounts/bad/summary").status_code == 400

    def should_reject_a_negative_page(self, client, gateway):
        assert client.get("/ibkr/accounts/U1/positions?page=-1").status_code == 422
        gateway.get_positions.assert_not_called()

    def should_expose_no_order_route(self, client):
        paths = client.app.openapi()["paths"]
        ibkr_paths = [path for path in paths if path.startswith("/ibkr")]

        assert len(ibkr_paths) == 6
        assert not [path for path in ibkr_paths if "order" in path or "reply" in path]
