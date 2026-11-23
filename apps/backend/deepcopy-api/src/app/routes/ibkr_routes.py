"""Read-only HTTP routes on the IBKR gateway."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.services.ibkr_gateway_service import IbkrGatewayService, ibkr_gateway

router = APIRouter(prefix="/ibkr", tags=["IBKR"])


def get_ibkr_gateway() -> IbkrGatewayService:
    """Dependency returning the shared gateway service."""
    return ibkr_gateway


Gateway = Annotated[IbkrGatewayService, Depends(get_ibkr_gateway)]


@router.get("/session", summary="Brokerage session status")
def session_status(
    gateway: Gateway,
) -> dict[str, Any]:
    return gateway.session_status()


@router.post("/session/init", summary="Open the brokerage session")
def init_session(
    gateway: Gateway,
) -> dict[str, Any]:
    return gateway.init_session()


@router.get("/accounts", summary="Portfolio accounts")
def list_accounts(
    gateway: Gateway,
) -> list[dict[str, Any]]:
    return gateway.list_accounts()


@router.get("/accounts/{account_id}/summary", summary="Account summary")
def get_summary(
    account_id: str,
    gateway: Gateway,
) -> dict[str, Any]:
    return gateway.get_summary(account_id)


@router.get("/accounts/{account_id}/positions", summary="Account positions")
def get_positions(
    account_id: str,
    gateway: Gateway,
    page: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    return gateway.get_positions(account_id, page)


@router.get("/contracts", summary="Search contracts by symbol")
def search_contracts(
    symbol: Annotated[str, Query(min_length=1, max_length=12)],
    gateway: Gateway,
) -> list[dict[str, Any]]:
    return gateway.search_contracts(symbol)
