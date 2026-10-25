"""Explicit public MCP tool adapter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from mcp.types import ToolAnnotations

from momentum_public_mcp.domain import (
    AnalysisDetail,
    AnalysisId,
    AnalysisPage,
    AnalysisSummary,
    MarketScan,
    Ratings,
    Suggestion,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)
from momentum_public_mcp.gateway import MomentumApiError, MomentumPublicGateway
from momentum_public_mcp.security import FingerprintProvider

Result = TypeVar("Result")

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
MODERATED_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)


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

    @tool(
        title="List analyses",
        tags={"public", "consultation"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def list_analyses(
        self,
        ticker: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnalysisSummary]:
        """List paginated Momentum analysis summaries.

        Args:
            ticker: Optional ticker symbol.
            limit: Number of results, between 1 and 200.
            offset: Number of results to skip.
        """
        return await self._translate(
            lambda: self._gateway.list_analyses(
                self._optional_ticker(ticker), AnalysisPage(limit, offset)
            ),
            transform=lambda summaries: summaries.as_list(),
        )

    @tool(
        title="Latest analyses",
        tags={"public", "consultation"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def latest_analyses(
        self,
        ticker: str | None = None,
        rating: str | None = None,
    ) -> list[AnalysisSummary]:
        """Get the most recent analysis for each ticker.

        Args:
            ticker: Optional ticker symbol.
            rating: Optional comma-separated portfolio ratings.
        """
        return await self._translate(
            lambda: self._gateway.latest_analyses(
                self._optional_ticker(ticker), self._optional_ratings(rating)
            ),
            transform=lambda summaries: summaries.as_list(),
        )

    @tool(
        title="Get analysis",
        tags={"public", "consultation"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def get_analysis(self, analysis_id: str) -> AnalysisDetail:
        """Get a complete Momentum analysis by UUID."""
        return await self._translate(
            lambda: self._gateway.get_analysis(AnalysisId.parse(analysis_id))
        )

    @tool(
        title="Get recommendations",
        tags={"public", "consultation"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def get_recommendations(
        self,
        rating: str = "Buy,Overweight",
        limit: int = 10,
    ) -> list[AnalysisSummary]:
        """Get latest analyses matching portfolio ratings.

        Args:
            rating: Comma-separated portfolio ratings.
            limit: Number of results, between 1 and 100.
        """
        return await self._translate(
            lambda: self._recommendations(rating, limit),
            transform=lambda summaries: summaries.as_list(),
        )

    @tool(
        title="Latest market scan",
        tags={"public", "market"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def latest_market_scan(self) -> MarketScan:
        """Get the most recent daily market regime and normalized asset signals."""
        return await self._translate(self._gateway.latest_market_scan)

    @tool(
        title="Suggest ticker",
        tags={"public", "suggestion"},
        annotations=MODERATED_WRITE,
        timeout=45,
    )
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

    @tool(
        title="Get suggestion status",
        tags={"public", "consultation"},
        annotations=READ_ONLY,
        timeout=45,
    )
    async def get_suggestion_status(self, suggestion_id: str) -> Suggestion:
        """Get the moderation status for a suggestion UUID."""
        return await self._translate(
            lambda: self._gateway.get_suggestion_status(
                SuggestionId.parse(suggestion_id)
            )
        )

    async def _recommendations(self, rating: str, limit: int):
        if not 1 <= limit <= 100:
            raise ValueError("Recommendation limit must be between 1 and 100.")
        return await self._gateway.get_recommendations(Ratings.from_csv(rating), limit)

    async def _translate(
        self,
        operation: Callable[[], Awaitable[Result]],
        transform: Callable[[Result], object] | None = None,
    ):
        try:
            result = await operation()
        except (MomentumApiError, ValueError) as error:
            raise ToolError(str(error)) from error
        if transform is None:
            return result
        return transform(result)

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
