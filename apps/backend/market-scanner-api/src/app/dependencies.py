"""FastAPI composition without import-time configuration or connections."""

from fastapi import Request

from app.services.market_scan_service import MarketScanService


def get_service(request: Request) -> MarketScanService:
    return MarketScanService(request.app.state.repository)
