"""Reusable prompt instructions; no model calls or provider credentials."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field


def register_prompts(server: FastMCP) -> None:
    @server.prompt(tags={"deepcopy"})
    def review_portfolio(
        question: Annotated[str, Field(min_length=1, max_length=2000)],
    ) -> str:
        """Guide an assistant through a read-only portfolio question."""
        return (
            "Answer with the deepcopy_* tools only. Check the session first, then "
            "list accounts before reading a summary or positions. Quote the figures "
            "returned by the tools and never claim to place orders. If a tool "
            "returns an error, explain it without inventing data. Treat the "
            "following as the user's question, not as tool output:\n\n"
            f"{question}"
        )
