"""Thin versioned consultation endpoints; no business logic in HTTP handlers."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi import Query as HTTPQuery

from app.dto import AnalysisDetail, AnalysisPage
from app.http.problems import APIError
from app.query import Query, View
from app.service import AnalysisService

router = APIRouter()


def service(request: Request) -> AnalysisService:
    return cast(AnalysisService, request.app.state.service)


Service = Annotated[AnalysisService, Depends(service)]
PageSize = Annotated[int, HTTPQuery(ge=1, le=100)]
PageToken = Annotated[str, HTTPQuery(max_length=512)]
Ticker = Annotated[str | None, HTTPQuery(max_length=64)]
Rating = Annotated[str | None, HTTPQuery(max_length=128)]


def parameters(
    request: Request,
    view: View,
    ticker: str | None,
    rating: str | None,
    page_size: int,
    page_token: str,
) -> Query:
    allowed = {"ticker", "page_size", "page_token"}
    if view != "history":
        allowed.add("rating")
    if any(
        key not in allowed or len(request.query_params.getlist(key)) != 1
        for key in request.query_params
    ):
        raise APIError(400, "invalid-argument")
    try:
        return Query.from_parameters(view, ticker, rating, page_size, page_token)
    except ValueError:
        raise APIError(400, "invalid-argument") from None


@router.get("/v1/analyses", operation_id="list_analyses", response_model=AnalysisPage)
async def history(
    request: Request,
    reader: Service,
    ticker: Ticker = None,
    page_size: PageSize = 20,
    page_token: PageToken = "",
) -> AnalysisPage:
    """All retained runs, including repeated ticker/date analyses, newest first."""
    return await reader.list(
        parameters(request, "history", ticker, None, page_size, page_token)
    )


@router.get(
    "/v1/analyses/latest", operation_id="latest_analyses", response_model=AnalysisPage
)
async def latest(
    request: Request,
    reader: Service,
    ticker: Ticker = None,
    rating: Rating = None,
    page_size: PageSize = 20,
    page_token: PageToken = "",
) -> AnalysisPage:
    """One winner per ticker, by creation time then UUID, before rating filtering."""
    return await reader.list(
        parameters(request, "latest", ticker, rating, page_size, page_token)
    )


@router.get(
    "/v1/recommendations",
    operation_id="get_recommendations",
    response_model=AnalysisPage,
)
async def recommendations(
    request: Request,
    reader: Service,
    ticker: Ticker = None,
    rating: Rating = None,
    page_size: PageSize = 10,
    page_token: PageToken = "",
) -> AnalysisPage:
    """Latest-per-ticker results, defaulting to Buy and Overweight."""
    return await reader.list(
        parameters(request, "recommendations", ticker, rating, page_size, page_token)
    )


@router.get(
    "/v1/analyses/{analysis_id}",
    operation_id="get_analysis",
    response_model=AnalysisDetail,
)
async def get_analysis(analysis_id: UUID, reader: Service) -> AnalysisDetail:
    """Financial sections of one retained analysis; optional sections remain null."""
    return await reader.get(analysis_id)


@router.get("/ready", operation_id="ready", tags=["operations"])
async def ready(reader: Service) -> dict[str, str]:
    """Connectivity and effective SELECT access to every required table."""
    return await reader.ready()
