"""Validated Momentum suggestion response model."""

from datetime import datetime
from uuid import UUID

from momentum_public_mcp.api.momentum.dtos.response.base import PublicResponse


class Suggestion(PublicResponse):
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None
