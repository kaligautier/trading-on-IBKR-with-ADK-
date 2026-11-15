"""Reusable prompts for consulting saved Momentum analyses."""

from fastmcp.exceptions import PromptError
from fastmcp.prompts import prompt

from momentum_public_mcp.constants import MOMENTUM_API_VERSION
from momentum_public_mcp.domain import TickerSymbol


@prompt(
    name="analyze_ticker",
    title="Summarize an existing ticker analysis",
    tags={"public", "consultation"},
    version=MOMENTUM_API_VERSION,
    meta={
        "upstream": {
            "api": "momentum",
            "api_version": MOMENTUM_API_VERSION,
        }
    },
)
def analyze_ticker(ticker: str) -> str:
    """Prepare an evidence-based summary of saved Momentum reports.

    Args:
        ticker: Ticker symbol to consult, for example AAPL.
    """
    try:
        symbol = TickerSymbol(ticker).value
    except ValueError as error:
        raise PromptError(str(error)) from error
    return (
        f"Ticker to consult: ticker={symbol}\n\n"
        "Use the saved Momentum reports available from the Momentum tools. "
        "Summarize their dates, ratings, evidence and stated risks. Do not start "
        "or imply that a new analysis has been started."
    )
