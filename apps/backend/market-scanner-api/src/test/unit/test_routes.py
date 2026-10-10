"""Exercise the HTTP contract independently from PostgreSQL."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.application import create_app
from app.config.settings import Settings
from app.models.market_scan import StoredScan

ROOT = Path(__file__).resolve().parents[6]
REPORT = json.loads(
    (ROOT / "apps/backend/market-scanner-adk/examples/report-v3.json").read_text()
)["market_regime"]
SCAN = StoredScan(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    scan_date=date(2026, 10, 5),
    created_at=datetime(2026, 10, 5, 7, tzinfo=UTC),
    report=REPORT,
)


class Repository:
    def __init__(self, scan=SCAN):
        self.scan = scan

    async def latest(self):
        return self.scan

    async def get(self, scan_id):
        return self.scan if self.scan and self.scan.id == scan_id else None

    async def list(self, page_size, cursor):
        from app.models.market_scan import ScanSummary

        return [
            ScanSummary(SCAN.id, SCAN.scan_date, SCAN.created_at, "cautious", "Summary")
        ]


def client(repository=None):
    return TestClient(
        create_app(
            Settings(
                DATABASE_URL="postgresql://market_scanner_reader:local@localhost/scanner",
                API_TOKEN="local-test-token",
                _env_file=None,
            ),
            repository=repository or Repository(),
        )
    )


HEADERS = {"Authorization": "Bearer local-test-token"}


def test_latest_preserves_the_persisted_report():
    with client() as api:
        response = api.get("/market-scans/latest", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["report"] == REPORT
    assert response.json()["id"] == str(SCAN.id)
    assert "session_id" not in response.json()


def test_absent_report_is_not_a_database_outage():
    with client(Repository(None)) as api:
        response = api.get("/market-scans/latest", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCAN_NOT_FOUND"


def test_health_is_public_but_reports_and_docs_require_authentication():
    with client() as api:
        assert api.get("/health").status_code == 200
        for path in ["/market-scans/latest", "/docs", "/openapi.json", "/ready"]:
            response = api.get(path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"


def test_database_errors_do_not_expose_credentials():
    class FailingRepository(Repository):
        async def latest(self):
            from app.repositories.market_scan_repository import StoreUnavailableError

            raise StoreUnavailableError() from RuntimeError("private-password")

    with client(FailingRepository()) as api:
        response = api.get("/market-scans/latest", headers=HEADERS)
    assert response.status_code == 503
    assert "private-password" not in response.text
    assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"


def test_detail_and_missing_identifier():
    with client() as api:
        assert (
            api.get(f"/market-scans/{SCAN.id}", headers=HEADERS).json()["report"]
            == REPORT
        )
        assert (
            api.get(
                "/market-scans/00000000-0000-0000-0000-000000000002", headers=HEADERS
            ).status_code
            == 404
        )
        assert api.get("/market-scans/not-a-uuid", headers=HEADERS).status_code == 422


def test_list_returns_bounded_summaries():
    with client() as api:
        response = api.get("/market-scans?page_size=1", headers=HEADERS)
        for query in ["page_size=0", "page_size=101", "page_token=bad"]:
            assert api.get("/market-scans?" + query, headers=HEADERS).status_code == 422
    assert response.status_code == 200
    assert response.json()["next_page_token"] == ""
    assert response.json()["items"][0]["id"] == str(SCAN.id)
    assert "report" not in response.json()["items"][0]


def test_invalid_stored_report_fails_instead_of_returning_incomplete_data():
    from dataclasses import replace

    with client(Repository(replace(SCAN, report={"schema_version": 99}))) as api:
        response = api.get("/market-scans/latest", headers=HEADERS)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INVALID_STORED_REPORT"


def test_request_correlation_is_bounded_and_secrets_are_not_logged(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="market_scanner_api"), client() as api:
        response = api.get(
            "/market-scans/latest", headers={**HEADERS, "X-Request-ID": "reader-test"}
        )
    assert response.headers["X-Request-ID"] == "reader-test"
    assert response.headers["cache-control"] == "no-store"
    assert "reader-test" in caplog.text
    assert "local-test-token" not in caplog.text
