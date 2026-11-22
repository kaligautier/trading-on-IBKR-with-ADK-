"""Versioned HTTP response DTOs for market scan resources."""

from datetime import date
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, JsonValue


class MarketScanResponse(BaseModel):
    """One persisted run; ``report`` is the stored v3 market regime object."""

    id: UUID
    scan_date: date
    created_at: AwareDatetime
    report: dict[str, JsonValue]


class ScanSummaryResponse(BaseModel):
    """One run in the history, without its full report."""

    id: UUID
    scan_date: date
    created_at: AwareDatetime
    regime: str
    summary: str


class ScanListResponse(BaseModel):
    """A history page; follow ``next_page_token`` until it is empty."""

    items: list[ScanSummaryResponse]
    next_page_token: str
