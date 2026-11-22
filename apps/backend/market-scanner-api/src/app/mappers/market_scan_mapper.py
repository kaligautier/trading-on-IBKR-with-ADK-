"""Map stored models to response DTOs; an invalid DTO raises an ``AppError``.

This is the only conversion point between stored records and HTTP DTOs, and it
never returns a partial response. A report that violates the v3 schema raises
``InvalidStoredReportError``; any other DTO validation failure raises
``InvalidResponseError``. Error details hold field paths only, never values.
"""

from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, JsonValue, ValidationError

from app.dto.response.market_scan_response import (
    MarketScanResponse,
    ScanListResponse,
    ScanSummaryResponse,
)
from app.models.market_scan import ScanSummary, StoredScan
from app.schemas.report import REPORT_VALIDATOR
from app.utils.error import InvalidResponseError, InvalidStoredReportError


def to_market_scan_response(scan: StoredScan) -> MarketScanResponse:
    """Map one stored scan after validating its report against the v3 schema."""
    _validate_report(scan.report)
    return _validated(
        MarketScanResponse,
        {
            "id": scan.id,
            "scan_date": scan.scan_date,
            "created_at": scan.created_at,
            "report": scan.report,
        },
    )


def to_scan_summary_response(summary: ScanSummary) -> ScanSummaryResponse:
    """Map one history row to its summary DTO."""
    return _validated(
        ScanSummaryResponse,
        {
            "id": summary.id,
            "scan_date": summary.scan_date,
            "created_at": summary.created_at,
            "regime": summary.regime,
            "summary": summary.summary,
        },
    )


def to_scan_list_response(
    items: list[ScanSummary], next_page_token: str
) -> ScanListResponse:
    """Map one history page and its opaque continuation token."""
    return _validated(
        ScanListResponse,
        {
            "items": [to_scan_summary_response(item) for item in items],
            "next_page_token": next_page_token,
        },
    )


def _validate_report(report: JsonValue) -> None:
    try:
        REPORT_VALIDATOR.validate(report)
    except SchemaValidationError as error:
        raise InvalidStoredReportError(details={"path": error.json_path}) from None


def _validated[DTO: BaseModel](dto: type[DTO], fields: dict[str, object]) -> DTO:
    try:
        return dto.model_validate(fields)
    except ValidationError as error:
        locations: list[JsonValue] = [
            ".".join(map(str, issue["loc"]))
            for issue in error.errors(include_url=False, include_input=False)
        ]
        raise InvalidResponseError(
            details={"dto": dto.__name__, "fields": locations}
        ) from None
