"""Explicit public MCP tool adapter."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastmcp.dependencies import CurrentContext
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field, ValidationError, ValidatorFunctionWrapHandler, WrapValidator

from app.api.momentum.config.constants import MOMENTUM_ANALYSIS_API_PREFIX
from app.api.momentum.dtos.response.analyses import (
    AnalysisDetail,
    ReaderPage,
)
from app.api.momentum.dtos.response.suggestions import Suggestion
from app.config.constants import (
    ANALYSIS_TOOL_OPTIONS,
    CONSULTATION_TOOL_OPTIONS,
    SUGGESTION_TOOL_OPTIONS,
)
from app.core_components.gateway import MomentumPublicGateway
from app.domain import (
    AnalysisId,
    AnalysisPage,
    Ratings,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)
from app.errors import AppError, InputError
from app.security import FingerprintProvider

Result = TypeVar("Result")


def _validate_page_size(value: object, handler: ValidatorFunctionWrapHandler) -> int:
    """Keep Pydantic constraints while presenting a concise MCP tool error."""
    try:
        return handler(value)
    except ValidationError as error:
        detail = error.errors(include_url=False, include_input=False)[0]
        match detail["type"]:
            case "less_than_equal":
                message = (
                    f"page_size doit être inférieur ou égal à {detail['ctx']['le']}."
                )
            case "greater_than_equal":
                message = (
                    f"page_size doit être supérieur ou égal à {detail['ctx']['ge']}."
                )
            case _:
                message = "page_size doit être un entier."
        raise ToolError(message, log_level=logging.WARNING) from None


PageSize = Annotated[
    int, Field(ge=1, le=100, strict=True), WrapValidator(_validate_page_size)
]
RecommendationPageSize = Annotated[
    int, Field(ge=1, le=50, strict=True), WrapValidator(_validate_page_size)
]
PageToken = Annotated[str, Field(max_length=512)]


class MomentumPublicTools:
    """Expose consultation and moderated suggestion capabilities only."""

    def __init__(
        self,
        gateway: MomentumPublicGateway,
        fingerprint: FingerprintProvider,
    ):
        self._gateway = gateway
        self._fingerprint = fingerprint

    def components(self) -> list[Callable]:
        return [
            self.list_analyses,
            self.latest_analyses,
            self.get_analysis,
            self.get_recommendations,
            self.suggest_ticker,
            self.get_suggestion_status,
        ]

    @tool(
        name="list_analyses",
        title="List analyses",
        description=(
            "Read one page of existing Momentum analysis history, optionally filtered "
            "by ticker. A ticker can have multiple analyses. Returns items and "
            "next_page_token; use an item's id with momentum_get_analysis for details. "
            "Continue with next_page_token unchanged as page_token and the same "
            "ticker filter. Only an empty next_page_token ends the list, even for "
            "a short or empty page."
        ),
        tags={"public", "momentum", "consultation", "analyses", "history"},
        meta={
            "upstream": {
                "api": "momentum",
                "method": "GET",
                "path": f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses",
            }
        },
        **ANALYSIS_TOOL_OPTIONS,
    )
    async def list_analyses(
        self,
        ticker: str | None = None,
        page_size: PageSize = 50,
        page_token: PageToken = "",
        ctx: Context = CurrentContext(),  # noqa: B008 -- FastMCP dependency marker
    ) -> ReaderPage:
        """Validate history filters and delegate one API page to the gateway.

        Args:
            ticker: Optional ticker symbol.
            page_size: Maximum analyses in this page, between 1 and 100.
            page_token: Opaque cursor from the previous page; empty starts the list.
        """
        return await self._translate(
            lambda: self._gateway.list_analyses(
                self._optional_ticker(ticker), AnalysisPage(page_size, page_token)
            ),
        )

    @tool(
        name="latest_analyses",
        title="Latest analyses",
        description=(
            "Read one page of the most recent existing Momentum analysis per ticker. "
            "Use ticker and rating to filter the selection. Returns items and "
            "next_page_token; use an item's id with momentum_get_analysis for details. "
            "Continue with next_page_token unchanged as page_token and the same "
            "ticker/rating filters. Only an empty next_page_token ends the list, "
            "even for a short or empty page."
        ),
        tags={"public", "momentum", "consultation", "analyses", "latest"},
        meta={
            "upstream": {
                "api": "momentum",
                "method": "GET",
                "path": f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses/latest",
            }
        },
        **ANALYSIS_TOOL_OPTIONS,
    )
    async def latest_analyses(
        self,
        ticker: str | None = None,
        rating: str | None = None,
        page_size: PageSize = 50,
        page_token: PageToken = "",
    ) -> ReaderPage:
        """Validate latest-per-ticker filters and delegate one API page.

        Args:
            ticker: Optional ticker symbol.
            rating: Optional comma-separated portfolio ratings.
            page_size: Maximum analyses in this page, between 1 and 100.
            page_token: Opaque cursor from the previous page; empty starts the list.
        """
        return await self._translate(
            lambda: self._gateway.latest_analyses(
                self._optional_ticker(ticker),
                self._optional_ratings(rating),
                AnalysisPage(page_size, page_token),
            ),
        )

    @tool(
        name="get_analysis",
        title="Get analysis",
        description=(
            "Read a complete existing Momentum analysis by UUID, including its "
            "technical, fundamental, sentiment, news and decision reports. Use an "
            "analysis id from momentum_list_analyses, momentum_latest_analyses or "
            "momentum_get_recommendations. This reads a saved report and does not "
            "start or refresh an analysis."
        ),
        tags={"public", "momentum", "consultation", "analyses", "detail"},
        meta={
            "upstream": {
                "api": "momentum",
                "method": "GET",
                "path": f"{MOMENTUM_ANALYSIS_API_PREFIX}/analyses/{{analysis_id}}",
            }
        },
        **ANALYSIS_TOOL_OPTIONS,
    )
    async def get_analysis(self, analysis_id: str) -> AnalysisDetail:
        """Validate the analysis UUID and retrieve its saved report.

        Args:
            analysis_id: Analysis UUID returned by a list tool's items.
        """
        return await self._translate(
            lambda: self._gateway.get_analysis(AnalysisId.parse(analysis_id))
        )

    @tool(
        name="get_recommendations",
        title="Get recommendations",
        description=(
            "Read one page of existing latest-per-ticker Momentum analyses matching "
            "portfolio ratings; defaults to Buy and Overweight. Returns saved "
            "recommendation summaries in items with next_page_token. "
            "Continue with next_page_token unchanged as page_token "
            "and the same rating filter. Only an empty next_page_token ends the "
            "list, even for a short or empty page."
        ),
        tags={"public", "momentum", "consultation", "analyses", "recommendations"},
        meta={
            "upstream": {
                "api": "momentum",
                "method": "GET",
                "path": f"{MOMENTUM_ANALYSIS_API_PREFIX}/recommendations",
            }
        },
        **ANALYSIS_TOOL_OPTIONS,
    )
    async def get_recommendations(
        self,
        rating: str = "Buy,Overweight",
        page_size: RecommendationPageSize = 10,
        page_token: PageToken = "",
    ) -> ReaderPage:
        """Validate portfolio ratings and delegate one recommendations page.

        Args:
            rating: Comma-separated portfolio ratings.
            page_size: Maximum analyses in this page, between 1 and 50.
            page_token: Opaque cursor from the previous page; empty starts the list.
        """
        return await self._translate(
            lambda: self._gateway.get_recommendations(
                Ratings.from_csv(rating), AnalysisPage(page_size, page_token)
            ),
        )

    @tool(
        name="suggest_ticker",
        title="Suggest ticker",
        description=(
            "Submit a ticker and optional reason for administrator review. A new "
            "suggestion remains pending and never starts an analysis. An existing "
            "suggestion for the same symbol is returned without updating it. "
            "Returns the suggestion UUID and moderation status; use that UUID "
            "with momentum_get_suggestion_status to follow the decision."
        ),
        tags={"public", "momentum", "suggestion", "moderation"},
        meta={
            "upstream": {"api": "momentum", "method": "POST", "path": "/suggestions"}
        },
        **SUGGESTION_TOOL_OPTIONS,
    )
    async def suggest_ticker(self, symbol: str, reason: str = "") -> Suggestion:
        """Validate a suggestion and pass the caller fingerprint to the gateway.

        Args:
            symbol: Ticker symbol to propose.
            reason: Optional rationale, at most 500 characters.
        """
        return await self._translate(
            lambda: self._gateway.suggest_ticker(
                TickerSymbol(symbol),
                SuggestionReason(reason),
                self._fingerprint.current(),
            )
        )

    @tool(
        name="get_suggestion_status",
        title="Get suggestion status",
        description=(
            "Read the current moderation status of a previously submitted "
            "suggestion. Use the suggestion UUID returned by momentum_suggest_ticker. "
            "This is a read-only lookup; it does not approve, reject or resubmit "
            "the suggestion."
        ),
        tags={"public", "momentum", "consultation", "suggestion", "status"},
        meta={
            "upstream": {
                "api": "momentum",
                "method": "GET",
                "path": "/suggestions/{suggestion_id}",
            }
        },
        **CONSULTATION_TOOL_OPTIONS,
    )
    async def get_suggestion_status(self, suggestion_id: str) -> Suggestion:
        """Validate a suggestion UUID and retrieve its moderation state.

        Args:
            suggestion_id: Suggestion UUID returned by momentum_suggest_ticker.
        """
        return await self._translate(
            lambda: self._gateway.get_suggestion_status(
                SuggestionId.parse(suggestion_id)
            )
        )

    async def _translate(
        self,
        operation: Callable[[], Awaitable[Result]],
    ) -> Result:
        try:
            return await operation()
        except InputError as error:
            raise ToolError(str(error), log_level=logging.WARNING) from error
        except AppError as error:
            raise ToolError(str(error)) from error

    @staticmethod
    def _optional_ticker(raw_ticker: str | None) -> TickerSymbol | None:
        if raw_ticker is None:
            return None
        return TickerSymbol(raw_ticker)

    @staticmethod
    def _optional_ratings(raw_ratings: str | None) -> Ratings | None:
        if raw_ratings is None:
            return None
        return Ratings.from_csv(raw_ratings)
