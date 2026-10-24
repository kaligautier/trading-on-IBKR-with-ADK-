"""Thin versioned consultation endpoints; no business logic in HTTP handlers."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi import Query as HTTPQuery

from app.domain.analyses.search import AnalysisSearchParams, View
from app.presentation.dto import AnalysisDetail, AnalysisPage
from app.presentation.http.problems import APIError
from app.presentation.mappers import detail_to_dto, page_to_dto
from app.services.analysis_service import AnalysisService

router = APIRouter()

LIST_PARAMETERS = frozenset({"ticker", "page_size", "page_token"})
QUERY_PARAMETERS = {
    "/v1/analyses": LIST_PARAMETERS,
    "/v1/analyses/latest": LIST_PARAMETERS | {"rating"},
    "/v1/recommendations": LIST_PARAMETERS | {"rating"},
}


def service(request: Request) -> AnalysisService:
    return cast(AnalysisService, request.app.state.service)


Service = Annotated[AnalysisService, Depends(service)]
PageSize = Annotated[int, HTTPQuery(ge=1, le=100)]
PageToken = Annotated[str, HTTPQuery(max_length=512)]
Ticker = Annotated[str | None, HTTPQuery(max_length=64)]
Rating = Annotated[str | None, HTTPQuery(max_length=128)]


def parameters(
    view: View,
    ticker: str | None,
    rating: str | None,
    page_size: int,
    page_token: str,
) -> AnalysisSearchParams:
    try:
        return AnalysisSearchParams.from_parameters(
            view, ticker, rating, page_size, page_token
        )
    except ValueError:
        raise APIError(400, "invalid-argument") from None


@router.get("/v1/analyses", operation_id="list_analyses", response_model=AnalysisPage)
async def history(
    reader: Service,
    ticker: Ticker = None,
    page_size: PageSize = 20,
    page_token: PageToken = "",
) -> AnalysisPage:
    """All retained runs, including repeated ticker/date analyses, newest first."""
    return page_to_dto(
        await reader.list(parameters("history", ticker, None, page_size, page_token))
    )


@router.get(
    "/v1/analyses/latest", operation_id="latest_analyses", response_model=AnalysisPage
)
async def latest(
    reader: Service,
    ticker: Ticker = None,
    rating: Rating = None,
    page_size: PageSize = 20,
    page_token: PageToken = "",
) -> AnalysisPage:
    """One winner per ticker, by creation time then UUID, before rating filtering."""
    return page_to_dto(
        await reader.list(parameters("latest", ticker, rating, page_size, page_token))
    )


@router.get(
    "/v1/recommendations",
    operation_id="get_recommendations",
    response_model=AnalysisPage,
)
async def recommendations(
    reader: Service,
    ticker: Ticker = None,
    rating: Rating = None,
    page_size: PageSize = 10,
    page_token: PageToken = "",
) -> AnalysisPage:
    """Latest-per-ticker results, defaulting to Buy and Overweight."""
    return page_to_dto(
        await reader.list(
            parameters("recommendations", ticker, rating, page_size, page_token)
        )
    )


@router.get(
    "/v1/analyses/{analysis_id}",
    operation_id="get_analysis",
    response_model=AnalysisDetail,
)
async def get_analysis(analysis_id: UUID, reader: Service) -> AnalysisDetail:
    """Financial sections of one retained analysis; optional sections remain null."""
    return detail_to_dto(await reader.get(analysis_id))


@router.get("/ready", operation_id="ready", tags=["operations"])
async def ready(reader: Service) -> dict[str, str]:
    """Connectivity and effective SELECT access to every required table."""
    await reader.ready()
    return {"status": "ready"}
