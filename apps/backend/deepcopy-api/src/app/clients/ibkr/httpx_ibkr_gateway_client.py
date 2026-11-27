"""httpx implementation of the IBKR gateway client."""

import logging
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from app.clients.ibkr.ibkr_gateway_client import IbkrGatewayClient
from app.config.settings import settings
from app.dto.ibkr.ibkr_dtos import (
    IbkrAccountDto,
    IbkrAuthStatusDto,
    IbkrContractDto,
    IbkrPositionDto,
    IbkrSummaryValueDto,
)
from app.utils.error import IbkrGatewayError, IbkrSessionError

logger = logging.getLogger(__name__)

NO_BRIDGE = "no bridge"
_ACCOUNTS = TypeAdapter(list[IbkrAccountDto])
_SUMMARY = TypeAdapter(dict[str, IbkrSummaryValueDto])
_POSITIONS = TypeAdapter(list[IbkrPositionDto])
_CONTRACTS = TypeAdapter(list[IbkrContractDto])


class HttpxIbkrGatewayClient(IbkrGatewayClient):
    """Call the gateway over HTTPS and parse its responses into DTOs."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def get_auth_status(self) -> IbkrAuthStatusDto:
        payload = self._request("POST", "/iserver/auth/status")
        return self._parse(IbkrAuthStatusDto.model_validate, payload)

    def init_brokerage_session(self) -> IbkrAuthStatusDto:
        payload = self._request(
            "POST",
            "/iserver/auth/ssodh/init",
            json={"publish": True, "compete": False},
        )
        return self._parse(IbkrAuthStatusDto.model_validate, payload)

    def list_accounts(self) -> list[IbkrAccountDto]:
        payload = self._request("GET", "/portfolio/accounts")
        return self._parse(_ACCOUNTS.validate_python, payload)

    def get_account_summary(self, account_id: str) -> dict[str, IbkrSummaryValueDto]:
        payload = self._request("GET", f"/portfolio/{account_id}/summary")
        return self._parse(_SUMMARY.validate_python, payload)

    def get_positions(self, account_id: str, page: int) -> list[IbkrPositionDto]:
        payload = self._request("GET", f"/portfolio/{account_id}/positions/{page}")
        return self._parse(_POSITIONS.validate_python, payload)

    def search_contracts(self, symbol: str) -> list[IbkrContractDto]:
        payload = self._request(
            "POST", "/iserver/secdef/search", json={"symbol": symbol}
        )
        return self._parse(_CONTRACTS.validate_python, payload)

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

    @staticmethod
    def _parse(validate, payload: Any):
        try:
            return validate(payload)
        except ValidationError as error:
            logger.warning("Unexpected IBKR gateway payload: %s", error.error_count())
            raise IbkrGatewayError("Unexpected IBKR gateway response") from error


def create_ibkr_gateway_client() -> IbkrGatewayClient:
    """Build the client from settings."""
    return HttpxIbkrGatewayClient(
        httpx.Client(
            base_url=settings.IBKR_GATEWAY_URL,
            verify=settings.IBKR_GATEWAY_VERIFY_TLS,
            timeout=settings.IBKR_GATEWAY_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    )
