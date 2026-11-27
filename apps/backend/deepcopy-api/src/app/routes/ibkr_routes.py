"""Read-only HTTP routes on the IBKR gateway."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dto.response.ibkr_responses import (
    AccountResponse,
    AccountSummaryResponse,
    ContractResponse,
    PositionResponse,
    SessionStatusResponse,
)
from app.services.ibkr_portfolio_service import (
    IbkrPortfolioService,
    ibkr_portfolio_service,
)

router = APIRouter(prefix="/ibkr", tags=["IBKR"])


def get_ibkr_portfolio_service() -> IbkrPortfolioService:
    """Dependency returning the shared portfolio service."""
    return ibkr_portfolio_service


Portfolio = Annotated[IbkrPortfolioService, Depends(get_ibkr_portfolio_service)]


@router.get("/session", summary="Brokerage session status")
def session_status(portfolio: Portfolio) -> SessionStatusResponse:
    return portfolio.session_status()


@router.post("/session/init", summary="Open the brokerage session")
def init_session(portfolio: Portfolio) -> SessionStatusResponse:
    return portfolio.init_session()


@router.get("/accounts", summary="Portfolio accounts")
def list_accounts(portfolio: Portfolio) -> list[AccountResponse]:
    return portfolio.list_accounts()


@router.get("/accounts/{account_id}/summary", summary="Account summary")
def get_summary(account_id: str, portfolio: Portfolio) -> AccountSummaryResponse:
    return portfolio.get_summary(account_id)


@router.get("/accounts/{account_id}/positions", summary="Account positions")
def get_positions(
    account_id: str,
    portfolio: Portfolio,
    page: Annotated[int, Query(ge=0)] = 0,
) -> list[PositionResponse]:
    return portfolio.get_positions(account_id, page)


@router.get("/contracts", summary="Search contracts by symbol")
def search_contracts(
    symbol: Annotated[str, Query(min_length=1, max_length=12)],
    portfolio: Portfolio,
) -> list[ContractResponse]:
    return portfolio.search_contracts(symbol)
