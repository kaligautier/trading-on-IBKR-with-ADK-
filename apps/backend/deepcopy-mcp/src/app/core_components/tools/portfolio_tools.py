"""Read-only MCP tools backed by the portfolio service."""

from collections.abc import Awaitable
from typing import Annotated, cast

from fastmcp import Context, FastMCP
from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from app.api.errors import UpstreamError
from app.models.identifiers import AccountId, Page, Symbol
from app.models.portfolio import (
    Account,
    AccountSummary,
    Contract,
    Position,
    SessionStatus,
)
from app.services.portfolio_service import PortfolioService

ACCOUNT_ID = Field(description="IBKR account ID from deepcopy_list_accounts")


def get_portfolio(ctx: Context = CurrentContext()) -> PortfolioService:
    return cast(PortfolioService, ctx.lifespan_context["portfolio"])


def read_only(title: str) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    )


async def call[Result](operation: Awaitable[Result]) -> Result:
    """Turn known upstream failures into actionable tool errors."""
    try:
        return await operation
    except UpstreamError as exc:
        raise ToolError(str(exc)) from None


def register_portfolio_tools(server: FastMCP) -> None:
    @server.tool(tags={"deepcopy"}, annotations=read_only("Get IBKR session"))
    async def deepcopy_get_session(
        service: PortfolioService = Depends(get_portfolio),
    ) -> SessionStatus:
        """Check whether the IBKR gateway session is signed in and open."""
        return await call(service.get_session())

    @server.tool(tags={"deepcopy"}, annotations=read_only("List IBKR accounts"))
    async def deepcopy_list_accounts(
        service: PortfolioService = Depends(get_portfolio),
    ) -> list[Account]:
        """List the IBKR portfolio accounts of the signed-in user."""
        return await call(service.list_accounts())

    @server.tool(tags={"deepcopy"}, annotations=read_only("Get IBKR account summary"))
    async def deepcopy_get_account_summary(
        account_id: Annotated[AccountId, ACCOUNT_ID],
        service: PortfolioService = Depends(get_portfolio),
    ) -> AccountSummary:
        """Read the net liquidation, cash and buying power of one account."""
        return await call(service.get_account_summary(account_id))

    @server.tool(tags={"deepcopy"}, annotations=read_only("Get IBKR positions"))
    async def deepcopy_get_positions(
        account_id: Annotated[AccountId, ACCOUNT_ID],
        page: Annotated[Page, Field(description="Page number, starting at 0")] = 0,
        service: PortfolioService = Depends(get_portfolio),
    ) -> list[Position]:
        """Read one page of positions of one IBKR account."""
        return await call(service.get_positions(account_id, page))

    @server.tool(tags={"deepcopy"}, annotations=read_only("Search IBKR contracts"))
    async def deepcopy_search_contracts(
        symbol: Annotated[Symbol, Field(description="Uppercase ticker, e.g. AAPL")],
        service: PortfolioService = Depends(get_portfolio),
    ) -> list[Contract]:
        """Search IBKR contracts by exact uppercase ticker symbol."""
        return await call(service.search_contracts(symbol))
