"""Validated Market Scanner read response model."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from momentum_public_mcp.api.momentum.dtos.response.base import PublicResponse


class MarketScan(PublicResponse):
    """Reader envelope; preserve report-v3 values, including decimal strings."""

    id: UUID
    scan_date: date
    created_at: datetime
    report: dict[str, Any]
