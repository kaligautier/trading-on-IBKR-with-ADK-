"""Typed provenance and availability of market observations."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class DataQuality(BaseModel):
    name: str
    symbol: str
    source: str
    source_url: str | None = None
    observed_on: date | None = None
    status: Literal["available", "stale", "unavailable"]
    reason: str | None = None
