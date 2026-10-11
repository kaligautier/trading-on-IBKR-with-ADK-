"""Typed request-state boundary and FastAPI dependency composition."""

from typing import cast

from fastapi import Request

from app.repositories.scan_reader import ScanReader
from app.services.market_scan_service import MarketScanService


def get_repository(request: Request) -> ScanReader:
    """Recover the reader installed by the application lifespan."""
    return cast(ScanReader, request.app.state.repository)


async def get_service(request: Request) -> MarketScanService:
    """Compose a use case without sending trivial work to the thread pool."""
    return MarketScanService(get_repository(request))
