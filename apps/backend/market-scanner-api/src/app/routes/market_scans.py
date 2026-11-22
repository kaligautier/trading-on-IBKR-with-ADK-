"""Market scan routes: thin, read-only HTTP layer over the consultation service.

Routes only validate HTTP input, resolve dependencies, call the service and map
the stored model to its response DTO. Invalid input (scan ID, page size or page
token length) is rejected by FastAPI with HTTP 422. They do not catch
``AppError``: the application handler maps it to its JSON body and HTTP status.
"""

from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.security import HTTPBearer

from app.dependencies import get_service
from app.dto.response.error_response import error_responses
from app.dto.response.market_scan_response import MarketScanResponse, ScanListResponse
from app.mappers.market_scan_mapper import (
    to_market_scan_response,
    to_scan_list_response,
)
from app.services.market_scan_service import MarketScanService
from app.utils.error import ErrorCode

API_PATH = "/market-scans"
API_VERSION = "v1"
API_PREFIX = f"/{API_VERSION}{API_PATH}"
API_TAGS: list[str | Enum] = ["market-scans"]

# Every route can fail authentication, storage access or unexpectedly.
COMMON_ERRORS = (
    ErrorCode.UNAUTHENTICATED,
    ErrorCode.INTERNAL_ERROR,
    ErrorCode.STORE_UNAVAILABLE,
)
router = APIRouter(
    prefix=API_PREFIX,
    tags=API_TAGS,
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "JSON representation excluded by Accept; no body"
        },
    },
)
ServiceDependency = Annotated[MarketScanService, Depends(get_service)]


@router.get(
    "/latest",
    response_model=MarketScanResponse,
    summary="Read the most recently persisted market scan",
    responses=error_responses(
        *COMMON_ERRORS,
        ErrorCode.SCAN_NOT_FOUND,
        ErrorCode.INVALID_STORED_REPORT,
        ErrorCode.INVALID_RESPONSE,
    ),
)
async def latest(service: ServiceDependency) -> MarketScanResponse:
    """Return the latest run, ordered by ``created_at`` then ``id``."""
    return to_market_scan_response(await service.latest_scan())


@router.get(
    "",
    response_model=ScanListResponse,
    summary="List persisted market scan summaries",
    responses=error_responses(
        *COMMON_ERRORS, ErrorCode.INVALID_ARGUMENT, ErrorCode.INVALID_RESPONSE
    ),
)
async def list_scans(
    service: ServiceDependency,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Number of summaries per page")
    ] = 20,
    page_token: Annotated[
        str, Query(max_length=512, description="Opaque token of the next page")
    ] = "",
) -> ScanListResponse:
    """Return one keyset page of run summaries, newest first."""
    items, next_page_token = await service.list_scans(page_size, page_token)
    return to_scan_list_response(items, next_page_token)


@router.get(
    "/{scan_id}",
    response_model=MarketScanResponse,
    summary="Read one persisted market scan",
    responses=error_responses(
        *COMMON_ERRORS,
        ErrorCode.SCAN_NOT_FOUND,
        ErrorCode.INVALID_ARGUMENT,
        ErrorCode.INVALID_STORED_REPORT,
        ErrorCode.INVALID_RESPONSE,
    ),
)
async def get_scan(
    scan_id: Annotated[UUID, Path(description="Persisted scan identifier")],
    service: ServiceDependency,
) -> MarketScanResponse:
    """Return one run and its report by UUID."""
    return to_market_scan_response(await service.get_scan(scan_id))
