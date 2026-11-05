"""Market Scanner response envelope."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MarketScan(BaseModel):
    """Reader envelope; preserve report-v3 values, including decimal strings."""

    id: UUID
    scan_date: date
    created_at: datetime
    report: dict[str, Any]
