"""Adapt MCP operations to the external APIs and aggregate reader pages."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from momentum_public_mcp.api.errors import MomentumApiError
from momentum_public_mcp.api.market_scanner.client.market_scanner_client import (
    MarketScannerClient,
)
from momentum_public_mcp.api.market_scanner.dtos.response.market_scan import MarketScan
from momentum_public_mcp.api.momentum.client.momentum_client import MomentumClient
from momentum_public_mcp.api.momentum.dtos.request.analyses import AnalysisPageRequest
from momentum_public_mcp.api.momentum.dtos.request.suggestions import SuggestionRequest
from momentum_public_mcp.api.momentum.dtos.response.analyses import (
    AnalysisDetail,
    AnalysisSummary,
    ReaderPage,
)
from momentum_public_mcp.api.momentum.dtos.response.suggestions import Suggestion
from momentum_public_mcp.domain import (
    AnalysisId,
    AnalysisPage,
    AnalysisSummaries,
    Ratings,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)


class MomentumPublicGateway(Protocol):
    async def latest_market_scan(self) -> MarketScan: ...
    async def list_analyses(
        self, ticker: TickerSymbol | None, page: AnalysisPage
    ) -> AnalysisSummaries: ...

    async def latest_analyses(
        self, ticker: TickerSymbol | None, ratings: Ratings | None
    ) -> AnalysisSummaries: ...

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail: ...

    async def get_recommendations(
        self, ratings: Ratings, limit: int
    ) -> AnalysisSummaries: ...

    async def suggest_ticker(
        self,
        symbol: TickerSymbol,
        reason: SuggestionReason,
        caller_fingerprint: str,
    ) -> Suggestion: ...

    async def get_suggestion_status(
        self, suggestion_id: SuggestionId
    ) -> Suggestion: ...


class MomentumHttpGateway:
    def __init__(self, momentum: MomentumClient, scanner: MarketScannerClient):
        self._momentum = momentum
        self._scanner = scanner

    async def list_analyses(
        self,
        ticker: TickerSymbol | None,
        page: AnalysisPage,
    ) -> AnalysisSummaries:
        request = AnalysisPageRequest(ticker=ticker.value if ticker else None)
        return await self._pages(
            self._momentum.list_analyses, request, page.limit, page.offset
        )

    async def latest_market_scan(self) -> MarketScan:
        return await self._scanner.latest_market_scan()

    async def latest_analyses(
        self,
        ticker: TickerSymbol | None,
        ratings: Ratings | None,
    ) -> AnalysisSummaries:
        request = AnalysisPageRequest(
            ticker=ticker.value if ticker else None,
            rating=ratings.as_csv() if ratings else None,
        )
        return await self._pages(self._momentum.latest_analyses, request)

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail:
        return await self._momentum.get_analysis(analysis_id.value)

    async def get_recommendations(
        self,
        ratings: Ratings,
        limit: int,
    ) -> AnalysisSummaries:
        request = AnalysisPageRequest(rating=ratings.as_csv())
        return await self._pages(self._momentum.get_recommendations, request, limit)

    async def suggest_ticker(
        self,
        symbol: TickerSymbol,
        reason: SuggestionReason,
        caller_fingerprint: str,
    ) -> Suggestion:
        request = SuggestionRequest(symbol=symbol.value, reason=reason.value)
        return await self._momentum.suggest_ticker(request, caller_fingerprint)

    async def get_suggestion_status(self, suggestion_id: SuggestionId) -> Suggestion:
        return await self._momentum.get_suggestion_status(suggestion_id.value)

    async def _pages(
        self,
        fetch_page: Callable[[AnalysisPageRequest], Awaitable[ReaderPage]],
        request: AnalysisPageRequest,
        limit: int | None = None,
        offset: int = 0,
    ) -> AnalysisSummaries:
        """Translate the original MCP window into the reader's cursor protocol.

        Never return a silently truncated latest-per-ticker result. The enclosing
        tool deadline bounds traversal; repeated cursors are an upstream error.
        """
        items: list[AnalysisSummary] = []
        token = ""
        seen: set[str] = set()
        while True:
            size = 100 if limit is None else min(100, offset + limit - len(items))
            page_request = request.model_copy(
                update={"page_size": size, "page_token": token}
            )
            page = await fetch_page(page_request)
            skipped = min(offset, len(page.items))
            offset -= skipped
            items.extend(page.items[skipped:])
            if not page.next_page_token or (limit is not None and len(items) >= limit):
                return AnalysisSummaries(tuple(items))
            token = page.next_page_token
            if token in seen:
                raise MomentumApiError(
                    "Momentum public API returned a repeated cursor."
                )
            seen.add(token)

    async def close(self) -> None:
        await self._momentum.close()
        await self._scanner.close()
