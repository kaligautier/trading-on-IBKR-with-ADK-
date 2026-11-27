"""ADK tool wrappers for the read-only IBKR portfolio service."""

from google.adk.tools import ToolContext
from google.adk.tools.function_tool import FunctionTool

from app.services.ibkr_portfolio_service import ibkr_portfolio_service
from app.utils.error import AppError, ToolExecutionError


def list_accounts(tool_context: ToolContext) -> list[dict]:
    """List the IBKR portfolio accounts of the signed-in user."""
    return _call(ibkr_portfolio_service.list_accounts)


def get_positions(account_id: str, tool_context: ToolContext) -> list[dict]:
    """Return the first page of positions of an IBKR account.

    Args:
        account_id: IBKR account ID returned by list_accounts.
    """
    return _call(ibkr_portfolio_service.get_positions, account_id)


def search_contracts(symbol: str, tool_context: ToolContext) -> list[dict]:
    """Search IBKR contracts by ticker symbol, for example AAPL.

    Args:
        symbol: Ticker symbol.
    """
    return _call(ibkr_portfolio_service.search_contracts, symbol)


def _call(operation, *args) -> list[dict]:
    try:
        return [item.model_dump() for item in operation(*args)]
    except AppError as error:
        raise ToolExecutionError(
            message=error.message, details=error.details
        ) from error


list_accounts_tool = FunctionTool(func=list_accounts)
get_positions_tool = FunctionTool(func=get_positions)
search_contracts_tool = FunctionTool(func=search_contracts)
