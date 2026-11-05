"""Reusable prompt templates; rendering them does not call an API or an LLM."""

from fastmcp.exceptions import PromptError
from fastmcp.prompts import prompt

from app.config.constants import ANALYZE_TICKER_INSTRUCTION
from app.core_components.prompts.instructions import get_instruction
from app.domain import TickerSymbol
from app.errors import AppError


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
