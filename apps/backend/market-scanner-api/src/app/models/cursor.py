"""Versioned keyset cursor; tokens contain no authorization or private state."""

import base64
import binascii
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError


class InvalidCursorError(ValueError):
    pass


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    created_at: AwareDatetime
    id: UUID

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode()

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        try:
            if not 1 <= len(value) <= 512:
                raise ValueError()
            raw = base64.b64decode(value, altchars=b"-_", validate=True)
            return cls.model_validate_json(raw)
        except (ValueError, binascii.Error, ValidationError):
            raise InvalidCursorError() from None

    @classmethod
    def from_row(cls, created_at: datetime, scan_id: UUID) -> "Cursor":
        return cls(created_at=created_at, id=scan_id)
