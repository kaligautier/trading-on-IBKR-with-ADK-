"""Stored model to response DTO mapping, including invalid DTO rejection."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.mappers.market_scan_mapper import (
    to_market_scan_response,
    to_scan_list_response,
)
from app.models.market_scan import ScanSummary, StoredScan
from app.utils.error import InvalidResponseError, InvalidStoredReportError

ROOT = Path(__file__).resolve().parents[6]
REPORT = json.loads(
    (ROOT / "apps/backend/market-scanner-adk/examples/report-v3.json").read_text()
)["market_regime"]
CREATED_AT = datetime(2026, 10, 5, 7, tzinfo=UTC)
SCAN = StoredScan(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    scan_date=date(2026, 10, 5),
    created_at=CREATED_AT,
    report=REPORT,
)
SUMMARY = ScanSummary(SCAN.id, SCAN.scan_date, CREATED_AT, "cautious", "Summary")


def test_scan_maps_to_response_and_preserves_the_report():
    response = to_market_scan_response(SCAN)
    assert response.id == SCAN.id
    assert response.created_at == CREATED_AT
    assert response.report == REPORT


@pytest.mark.parametrize(
    "report,path",
    [
        ({"schema_version": 99}, "$"),
        (["not", "an", "object"], "$"),
        (
            {**REPORT, "scope": {**REPORT["scope"], "observation_dates": ["x"]}},
            "$.scope.observation_dates",
        ),
    ],
)
def test_invalid_report_raises_with_its_schema_path(report, path):
    with pytest.raises(InvalidStoredReportError) as error:
        to_market_scan_response(replace(SCAN, report=report))
    assert error.value.details["path"].startswith(path)


def test_invalid_scan_dto_raises_with_field_paths_only():
    with pytest.raises(InvalidResponseError) as error:
        to_market_scan_response(replace(SCAN, created_at=datetime(2026, 10, 5, 7)))
    assert error.value.details == {
        "dto": "MarketScanResponse",
        "fields": ["created_at"],
    }


def test_summaries_map_to_a_list_response():
    response = to_scan_list_response([SUMMARY], "next")
    assert response.next_page_token == "next"
    assert response.items[0].regime == "cautious"


def test_invalid_summary_dto_raises_instead_of_returning_a_partial_page():
    with pytest.raises(InvalidResponseError) as error:
        to_scan_list_response([replace(SUMMARY, regime=None)], "")
    assert error.value.details == {
        "dto": "ScanSummaryResponse",
        "fields": ["regime"],
    }
