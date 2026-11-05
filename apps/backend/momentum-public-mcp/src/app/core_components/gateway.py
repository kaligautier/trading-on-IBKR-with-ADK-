"""Adapt MCP operations to the external APIs, one reader page per call."""

from typing import Protocol

from app.api.market_scanner.client.market_scanner_client import (
    MarketScannerClient,
)
from app.api.market_scanner.dtos.response.market_scan import MarketScan
from app.api.momentum.client.momentum_client import MomentumClient
from app.api.momentum.dtos.request.analyses import AnalysisPageRequest
from app.api.momentum.dtos.request.suggestions import SuggestionRequest
from app.api.momentum.dtos.response.analyses import (
    AnalysisDetail,
    ReaderPage,
)
from app.api.momentum.dtos.response.suggestions import Suggestion
from app.domain import (
    AnalysisId,
    AnalysisPage,
    Ratings,
    SuggestionId,
    SuggestionReason,
    TickerSymbol,
)


class MomentumPublicGateway(Protocol):
    async def latest_market_scan(self) -> MarketScan: ...
    async def list_analyses(
        self, ticker: TickerSymbol | None, page: AnalysisPage
    ) -> ReaderPage: ...

    async def latest_analyses(
        self, ticker: TickerSymbol | None, ratings: Ratings | None, page: AnalysisPage
    ) -> ReaderPage: ...

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail: ...

    async def get_recommendations(
        self, ratings: Ratings, page: AnalysisPage
    ) -> ReaderPage: ...

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
    ) -> ReaderPage:
        request = AnalysisPageRequest(
            ticker=ticker.value if ticker else None,
            page_size=page.page_size,
            page_token=page.page_token,
        )
        return await self._momentum.list_analyses(request)

    async def latest_market_scan(self) -> MarketScan:
        return await self._scanner.latest_market_scan()

    async def latest_analyses(
        self,
        ticker: TickerSymbol | None,
        ratings: Ratings | None,
        page: AnalysisPage,
    ) -> ReaderPage:
        request = AnalysisPageRequest(
            ticker=ticker.value if ticker else None,
            rating=ratings.as_csv() if ratings else None,
            page_size=page.page_size,
            page_token=page.page_token,
        )
        return await self._momentum.latest_analyses(request)

    async def get_analysis(self, analysis_id: AnalysisId) -> AnalysisDetail:
        return await self._momentum.get_analysis(analysis_id.value)

    async def get_recommendations(
        self,
        ratings: Ratings,
        page: AnalysisPage,
    ) -> ReaderPage:
        request = AnalysisPageRequest(
            rating=ratings.as_csv(),
            page_size=page.page_size,
            page_token=page.page_token,
        )
        return await self._momentum.get_recommendations(request)

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

    async def close(self) -> None:
        await self._momentum.close()
        await self._scanner.close()
