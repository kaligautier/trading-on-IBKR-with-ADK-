"""Stored records, independent of HTTP and of the ADK runtime."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from pydantic import JsonValue


@dataclass(frozen=True)
class StoredScan:
    id: UUID
    scan_date: date
    created_at: datetime
    report: dict[str, JsonValue]


@dataclass(frozen=True)
class ScanSummary:
    id: UUID
    scan_date: date
    created_at: datetime
    regime: str
    summary: str
