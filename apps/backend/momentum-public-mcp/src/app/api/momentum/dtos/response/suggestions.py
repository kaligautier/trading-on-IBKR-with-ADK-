"""Public Momentum suggestion response."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Suggestion(BaseModel):
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None
