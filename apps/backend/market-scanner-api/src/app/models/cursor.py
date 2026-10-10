"""Versioned keyset cursor; tokens contain no authorization or private state."""

import base64
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict


class InvalidCursorError(ValueError):
    """A pagination token is malformed or uses an unsupported version."""


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    created_at: AwareDatetime
    id: UUID

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode()

    @classmethod
    def decode(cls, value: str) -> Self:
        try:
            if not 1 <= len(value) <= 512:
                raise ValueError()
            raw = base64.b64decode(value, altchars=b"-_", validate=True)
            return cls.model_validate_json(raw)
        except ValueError:
            raise InvalidCursorError() from None

    @classmethod
    def from_row(cls, created_at: datetime, scan_id: UUID) -> Self:
        return cls(created_at=created_at, id=scan_id)
