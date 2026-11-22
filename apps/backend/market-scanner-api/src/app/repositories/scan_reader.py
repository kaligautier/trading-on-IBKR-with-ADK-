"""Storage contract consumed by consultation use cases, without SQL dependencies."""

from typing import Protocol
from uuid import UUID

from app.models.cursor import Cursor
from app.models.market_scan import ScanSummary, StoredScan


class ScanReader(Protocol):
    async def latest(self) -> StoredScan | None: ...
    async def get(self, scan_id: UUID) -> StoredScan | None: ...
    async def list(
        self, page_size: int, cursor: Cursor | None
    ) -> list[ScanSummary]: ...
