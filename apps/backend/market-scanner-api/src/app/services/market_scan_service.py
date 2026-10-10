"""Consultation use cases; no SQL, HTTP or model invocation."""

from uuid import UUID

from app.models.cursor import Cursor
from app.models.market_scan import ScanSummary, StoredScan
from app.repositories.market_scan_repository import ScanReader


class ScanNotFoundError(Exception):
    """No persisted run matches the request."""


class MarketScanService:
    def __init__(self, repository: ScanReader) -> None:
        self._repository = repository

    async def latest_scan(self) -> StoredScan:
        scan = await self._repository.latest()
        if scan is None:
            raise ScanNotFoundError()
        return scan

    async def get_scan(self, scan_id: UUID) -> StoredScan:
        scan = await self._repository.get(scan_id)
        if scan is None:
            raise ScanNotFoundError()
        return scan

    async def list_scans(
        self, page_size: int, page_token: str
    ) -> tuple[list[ScanSummary], str]:
        cursor = Cursor.decode(page_token) if page_token else None
        rows = await self._repository.list(page_size, cursor)
        items = rows[:page_size]
        next_token = ""
        if len(rows) > page_size:
            last = items[-1]
            next_token = Cursor.from_row(last.created_at, last.id).encode()
        return items, next_token
