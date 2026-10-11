"""Preserve report v3 JSON exactly, including decimal strings and nulls."""

import json
from datetime import date
from importlib.resources import files
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from pydantic import AwareDatetime, BaseModel, ConfigDict, JsonValue

from app.models.market_scan import ScanSummary, StoredScan

REPORT_SCHEMA = json.loads(files("app.schemas").joinpath("report-v3.json").read_text())
VALIDATOR = Draft202012Validator(REPORT_SCHEMA, format_checker=FormatChecker())


class InvalidStoredReportError(Exception):
    """A stored report violates the supported writer contract."""


class MarketScanResponse(BaseModel):
    id: UUID
    scan_date: date
    created_at: AwareDatetime
    report: dict[str, JsonValue]


def assemble(scan: StoredScan) -> MarketScanResponse:
    if not isinstance(scan.report, dict):
        raise InvalidStoredReportError()
    try:
        VALIDATOR.validate(scan.report)
    except ValidationError:
        raise InvalidStoredReportError() from None
    return MarketScanResponse(
        id=scan.id,
        scan_date=scan.scan_date,
        created_at=scan.created_at,
        report=scan.report,
    )


class ScanSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scan_date: date
    created_at: AwareDatetime
    regime: str
    summary: str


class ScanListResponse(BaseModel):
    items: list[ScanSummaryResponse]
    next_page_token: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def assemble_list(items: list[ScanSummary], next_page_token: str) -> ScanListResponse:
    return ScanListResponse(
        items=[ScanSummaryResponse.model_validate(item) for item in items],
        next_page_token=next_page_token,
    )
