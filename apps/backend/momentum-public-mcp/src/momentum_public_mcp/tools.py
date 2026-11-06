"""Explicit public MCP tool adapter."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field, ValidationError, ValidatorFunctionWrapHandler, WrapValidator

from momentum_public_mcp.constants import (
    GET_ANALYSIS_TOOL,
    GET_RECOMMENDATIONS_TOOL,
    GET_SUGGESTION_STATUS_TOOL,
    LATEST_ANALYSES_TOOL,
    LATEST_MARKET_SCAN_TOOL,
    LIST_ANALYSES_TOOL,
    SUGGEST_TICKER_TOOL,
)
from momentum_public_mcp.domain import (
    AnalysisDetail,
    AnalysisId,
    AnalysisPage,
    AnalysisSummaries,
    MarketScan,
    Ratings,
    Suggestion,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)
from momentum_public_mcp.gateway import MomentumApiError, MomentumPublicGateway
from momentum_public_mcp.observability import record_result
from momentum_public_mcp.security import FingerprintProvider

Result = TypeVar("Result")


def _validate_page_size(value: object, handler: ValidatorFunctionWrapHandler) -> int:
    """Use clear tool errors while retaining schema constraints in tools/list."""
    try:
        return handler(value)
    except ValidationError as error:
        detail = error.errors(include_url=False, include_input=False)[0]
        if detail["type"] == "less_than_equal":
            message = f"page_size doit être inférieur ou égal à {detail['ctx']['le']}."
        elif detail["type"] == "greater_than_equal":
            message = f"page_size doit être supérieur ou égal à {detail['ctx']['ge']}."
        else:
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
            self.latest_market_scan,
            self.suggest_ticker,
            self.get_suggestion_status,
        ]

    @tool(**LIST_ANALYSES_TOOL)
    async def list_analyses(
        self,
        ticker: str | None = None,
        page_size: PageSize = 50,
        page_token: PageToken = "",
    ) -> AnalysisSummaries:
        """Read one page of Momentum history and return its API cursor.

        Args:
            ticker: Optional ticker symbol.
            page_size: Maximum items in this page, between 1 and 100.
            page_token: Opaque cursor from the prior page; empty starts the list.
        """
        return await self._translate(
            lambda: self._gateway.list_analyses(
                self._optional_ticker(ticker), AnalysisPage(page_size, page_token)
            )
        )

    @tool(**LATEST_ANALYSES_TOOL)
    async def latest_analyses(
        self,
        ticker: str | None = None,
        rating: str | None = None,
        page_size: PageSize = 50,
        page_token: PageToken = "",
    ) -> AnalysisSummaries:
        """Read one page of the latest analysis for each ticker.

        Args:
            ticker: Optional ticker symbol.
            rating: Optional comma-separated portfolio ratings.
            page_size: Maximum items in this page, between 1 and 100.
            page_token: Opaque cursor from the prior page; empty starts the list.
        """
        return await self._translate(
            lambda: self._gateway.latest_analyses(
                self._optional_ticker(ticker),
                self._optional_ratings(rating),
                AnalysisPage(page_size, page_token),
            )
        )

    @tool(**GET_ANALYSIS_TOOL)
    async def get_analysis(self, analysis_id: str) -> AnalysisDetail:
        """Get a complete Momentum analysis by UUID."""
        return await self._translate(
            lambda: self._gateway.get_analysis(AnalysisId.parse(analysis_id))
        )

    @tool(**GET_RECOMMENDATIONS_TOOL)
    async def get_recommendations(
        self,
        rating: str = "Buy,Overweight",
        page_size: RecommendationPageSize = 10,
        page_token: PageToken = "",
    ) -> AnalysisSummaries:
        """Read one page of latest analyses matching portfolio ratings.

        Args:
            rating: Comma-separated portfolio ratings.
            page_size: Maximum items in this page, between 1 and 50.
            page_token: Opaque cursor from the prior page; empty starts the list.
        """
        return await self._translate(
            lambda: self._recommendations(rating, page_size, page_token)
        )

    @tool(**LATEST_MARKET_SCAN_TOOL)
    async def latest_market_scan(self) -> MarketScan:
        """Get the most recent daily market regime and normalized asset signals."""
        return await self._translate(self._gateway.latest_market_scan)

    @tool(**SUGGEST_TICKER_TOOL)
    async def suggest_ticker(self, symbol: str, reason: str = "") -> Suggestion:
        """Suggest a ticker for administrator review without starting an analysis.

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

    @tool(**GET_SUGGESTION_STATUS_TOOL)
    async def get_suggestion_status(self, suggestion_id: str) -> Suggestion:
        """Get the moderation status for a suggestion UUID."""
        return await self._translate(
            lambda: self._gateway.get_suggestion_status(
                SuggestionId.parse(suggestion_id)
            )
        )

    async def _recommendations(self, rating: str, page_size: int, page_token: str):
        page = AnalysisPage(page_size, page_token)
        if page.page_size > 50:
            raise ValueError("Recommendation page size must be at most 50.")
        return await self._gateway.get_recommendations(Ratings.from_csv(rating), page)

    async def _translate(
        self,
        operation: Callable[[], Awaitable[Result]],
    ):
        try:
            result = await operation()
        except (MomentumApiError, ValueError) as error:
            raise ToolError(str(error)) from error
        record_result(result)
        return result

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
