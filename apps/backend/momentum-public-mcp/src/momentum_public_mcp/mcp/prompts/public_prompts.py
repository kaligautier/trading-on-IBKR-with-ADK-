"""Reusable prompt templates; rendering them does not call an API or an LLM."""

from fastmcp.exceptions import PromptError
from fastmcp.prompts import prompt

from momentum_public_mcp.config.constants import ANALYZE_TICKER_INSTRUCTION
from momentum_public_mcp.domain import TickerSymbol
from momentum_public_mcp.errors import AppError
from momentum_public_mcp.mcp.prompts.instructions import get_instruction


@prompt(title="Summarize an existing ticker analysis", tags={"public", "consultation"})
def analyze_ticker(ticker: str) -> str:
    """Prepare an evidence-based summary of existing Momentum reports.

    Args:
        ticker: Ticker symbol to consult, for example AAPL.
    """
    try:
        symbol = TickerSymbol(ticker).value
        instructions = get_instruction(ANALYZE_TICKER_INSTRUCTION)
    except (AppError, ValueError) as error:
        raise PromptError(str(error)) from error
    return f"Ticker to consult: ticker={symbol}\n\n{instructions}"
