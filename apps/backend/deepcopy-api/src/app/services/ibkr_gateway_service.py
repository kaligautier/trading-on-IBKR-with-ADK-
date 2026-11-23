"""Read-only client for one IBKR Client Portal gateway.

The gateway is started and signed in by an operator. This service never calls
order, reply or login endpoints.
"""

import logging
import re
from typing import Any

import httpx

from app.config.settings import settings
from app.utils.error import IbkrGatewayError, IbkrSessionError, InvalidInputError

logger = logging.getLogger(__name__)

ACCOUNT_ID_PATTERN = re.compile(r"^[A-Z0-9]{1,20}$")
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,12}$")
NO_BRIDGE = "no bridge"


class IbkrGatewayService:
    """Business operations on the IBKR gateway, independent of FastAPI and ADK."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def session_status(self) -> dict[str, Any]:
        """Return the brokerage session status."""
        return self._request("POST", "/iserver/auth/status")

    def init_session(self) -> dict[str, Any]:
        """Open the brokerage session without taking over another one."""
        return self._request(
            "POST",
            "/iserver/auth/ssodh/init",
            json={"publish": True, "compete": False},
        )

    def list_accounts(self) -> list[dict[str, Any]]:
        """List the portfolio accounts of the signed-in user."""
        return self._request("GET", "/portfolio/accounts")

    def get_summary(self, account_id: str) -> dict[str, Any]:
        """Return the summary of one account."""
        return self._request("GET", f"/portfolio/{_account_id(account_id)}/summary")

    def get_positions(self, account_id: str, page: int = 0) -> list[dict[str, Any]]:
        """Return one page of positions of one account."""
        if page < 0:
            raise InvalidInputError("page must be zero or positive", {"page": page})
        return self._request(
            "GET", f"/portfolio/{_account_id(account_id)}/positions/{page}"
        )

    def search_contracts(self, symbol: str) -> list[dict[str, Any]]:
        """Search contracts by ticker symbol."""
        return self._request(
            "POST", "/iserver/secdef/search", json={"symbol": _symbol(symbol)}
        )

    def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        if method == "POST" and json is None:
            json = {}
        try:
            response = self._client.request(method, path, json=json)
        except httpx.HTTPError as error:
            logger.warning("IBKR gateway unreachable on %s %s", method, path)
            raise IbkrGatewayError(details={"path": path}) from error
        if response.status_code == 401:
            raise IbkrSessionError(
                "IBKR session is not authenticated: sign in at the gateway",
                {"path": path},
            )
        if response.status_code == 400 and NO_BRIDGE in response.text:
            raise IbkrSessionError(
                "IBKR brokerage session is not open: call POST /ibkr/session/init",
                {"path": path},
            )
        if response.status_code >= 400:
            logger.warning(
                "IBKR gateway returned %s on %s %s",
                response.status_code,
                method,
                path,
            )
            raise IbkrGatewayError(
                details={"path": path, "gateway_status": response.status_code}
            )
        return response.json()


def _account_id(account_id: str) -> str:
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise InvalidInputError("Invalid IBKR account ID", {"field": "account_id"})
    return account_id


def _symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(normalized):
        raise InvalidInputError("Invalid ticker symbol", {"symbol": symbol})
    return normalized


def create_ibkr_gateway_service() -> IbkrGatewayService:
    """Build the service from settings."""
    client = httpx.Client(
        base_url=settings.IBKR_GATEWAY_URL,
        verify=settings.IBKR_GATEWAY_VERIFY_TLS,
        timeout=settings.IBKR_GATEWAY_TIMEOUT_SECONDS,
        follow_redirects=False,
    )
    return IbkrGatewayService(client)


ibkr_gateway = create_ibkr_gateway_service()
