from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer

from app.dependencies import get_service
from app.dto.response.market_scan_response_assembler import (
    ErrorResponse,
    MarketScanResponse,
    ScanListResponse,
    ScanSummaryResponse,
    assemble,
)
from app.services.market_scan_service import MarketScanService

router = APIRouter(
    prefix="/market-scans",
    tags=["market-scans"],
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Scan not found"},
        422: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Invalid stored report"},
        503: {"model": ErrorResponse, "description": "Storage unavailable"},
    },
)
Service = Annotated[MarketScanService, Depends(get_service)]


@router.get("/latest", response_model=MarketScanResponse)
async def latest(service: Service) -> MarketScanResponse:
    return assemble(await service.latest_scan())


@router.get("", response_model=ScanListResponse)
async def list_scans(
    service: Service,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    page_token: Annotated[str, Query(max_length=512)] = "",
) -> ScanListResponse:
    items, next_token = await service.list_scans(page_size, page_token)
    return ScanListResponse(
        items=[ScanSummaryResponse.model_validate(item) for item in items],
        next_page_token=next_token,
    )


@router.get("/{scan_id}", response_model=MarketScanResponse)
async def get_scan(scan_id: UUID, service: Service) -> MarketScanResponse:
    return assemble(await service.get_scan(scan_id))
