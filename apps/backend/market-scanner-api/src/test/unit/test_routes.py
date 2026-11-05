"""Exercise the HTTP contract independently from PostgreSQL."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest
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
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["report"] == REPORT
    assert response.json()["id"] == str(SCAN.id)
    assert "session_id" not in response.json()


@pytest.mark.parametrize("arbitration", ["missing", "null", "populated"])
def test_reader_preserves_new_and_legacy_arbitration_without_inventing_it(arbitration):
    report = deepcopy(REPORT)
    if arbitration == "missing":
        report.pop("arbitration")
    elif arbitration == "null":
        report["arbitration"] = None
    with client(Repository(replace(SCAN, report=report))) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["report"] == report


@pytest.mark.parametrize(
    "field, value",
    [
        ("decision_rationale", "   "),
        ("decision_rationale", "x" * 501),
        ("main_counterargument", ""),
        ("supporting_factors", []),
        ("supporting_factors", ["Observation"] * 4),
        ("supporting_factors", ["   "]),
        ("invalidation_conditions", ["Condition"] * 4),
        ("invalidation_conditions", [""]),
        ("research_critique", {"challenges": []}),
    ],
)
def test_reader_rejects_malformed_public_arbitration(field, value):
    report = deepcopy(REPORT)
    report["arbitration"][field] = value
    with client(Repository(replace(SCAN, report=report))) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INVALID_STORED_REPORT"


def test_absent_report_is_not_a_database_outage():
    with client(Repository(None)) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCAN_NOT_FOUND"


def test_health_is_public_but_reports_and_docs_require_authentication():
    with client() as api:
        assert api.get("/health").status_code == 200
        for path in ["/v1/market-scans/latest", "/docs", "/openapi.json", "/ready"]:
            response = api.get(path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"


def test_database_errors_do_not_expose_credentials():
    class FailingRepository(Repository):
        async def latest(self):
            from app.repositories.scan_reader import StoreUnavailableError

            raise StoreUnavailableError() from RuntimeError("private-password")

    with client(FailingRepository()) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 503
    assert "private-password" not in response.text
    assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"


def test_detail_and_missing_identifier():
    with client() as api:
        assert (
            api.get(f"/v1/market-scans/{SCAN.id}", headers=HEADERS).json()["report"]
            == REPORT
        )
        assert (
            api.get(
                "/v1/market-scans/00000000-0000-0000-0000-000000000002", headers=HEADERS
            ).status_code
            == 404
        )
        assert (
            api.get("/v1/market-scans/not-a-uuid", headers=HEADERS).status_code == 422
        )


def test_list_returns_bounded_summaries():
    with client() as api:
        response = api.get("/v1/market-scans?page_size=1", headers=HEADERS)
        for query in ["page_size=0", "page_size=101", "page_token=bad"]:
            assert (
                api.get("/v1/market-scans?" + query, headers=HEADERS).status_code == 422
            )
    assert response.status_code == 200
    assert response.json()["next_page_token"] == ""
    assert response.json()["items"][0]["id"] == str(SCAN.id)
    assert "report" not in response.json()["items"][0]


def test_invalid_stored_report_fails_instead_of_returning_incomplete_data():
    from dataclasses import replace

    with client(Repository(replace(SCAN, report={"schema_version": 99}))) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INVALID_STORED_REPORT"


def test_request_correlation_is_bounded_and_secrets_are_not_logged(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="market_scanner_api"), client() as api:
        response = api.get(
            "/v1/market-scans/latest",
            headers={**HEADERS, "X-Request-ID": "reader-test"},
        )
    assert response.headers["X-Request-ID"] == "reader-test"
    assert response.headers["cache-control"] == "no-store"
    assert "reader-test" in caplog.text
    assert "local-test-token" not in caplog.text


def test_unexpected_errors_are_sanitized_and_still_correlated(caplog):
    import logging

    class BrokenRepository(Repository):
        async def latest(self):
            raise RuntimeError("private-password")

    with (
        caplog.at_level(logging.INFO, logger="market_scanner_api"),
        client(BrokenRepository()) as api,
    ):
        response = api.get(
            "/v1/market-scans/latest",
            headers={**HEADERS, "X-Request-ID": "failed-request"},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.headers["X-Request-ID"] == "failed-request"
    assert '"status": 500' in caplog.text
    assert "private-password" not in response.text + caplog.text


def test_stored_dates_are_validated_not_just_treated_as_strings():
    from copy import deepcopy
    from dataclasses import replace

    report = deepcopy(REPORT)
    report["scope"]["observation_dates"] = ["2026-02-30"]
    with client(Repository(replace(SCAN, report=report))) as api:
        response = api.get("/v1/market-scans/latest", headers=HEADERS)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INVALID_STORED_REPORT"


def test_framework_errors_use_the_same_envelope():
    with client() as api:
        missing = api.get("/unknown", headers=HEADERS)
        disallowed = api.post("/v1/market-scans/latest", headers=HEADERS)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert disallowed.status_code == 405
    assert disallowed.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in disallowed.headers["allow"]


@pytest.mark.parametrize(
    "path", ["/market-scans", "/market-scans/latest", f"/market-scans/{SCAN.id}"]
)
def test_unversioned_business_paths_are_removed(path):
    with client() as api:
        assert api.get(path, headers=HEADERS).status_code == 404


@pytest.mark.parametrize(
    "path",
    ["/v1/market-scans", "/v1/market-scans/latest", f"/v1/market-scans/{SCAN.id}"],
)
def test_versioned_head_and_allow(path):
    with client() as api:
        get = api.get(path, headers=HEADERS)
        head = api.head(path, headers=HEADERS)
        disallowed = api.post(path, headers=HEADERS)
    assert head.status_code == get.status_code == 200
    assert head.content == b""
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["content-length"] == get.headers["content-length"]
    assert disallowed.status_code == 405
    assert set(disallowed.headers["allow"].replace(" ", "").split(",")) == {
        "GET",
        "HEAD",
    }


@pytest.mark.parametrize(
    "accept,status",
    [
        ("text/html", 406),
        ("application/json;q=0,*/*;q=1", 406),
        ("application/*", 200),
        ("application/json;charset=utf-8", 200),
    ],
)
def test_json_representation_negotiation(accept, status):
    with client() as api:
        response = api.get(
            "/v1/market-scans/latest", headers={**HEADERS, "Accept": accept}
        )
    assert response.status_code == status
    assert response.headers["vary"] == "Accept"


def test_openapi_only_exposes_canonical_business_resources():
    with client() as api:
        paths = api.get("/openapi.json", headers=HEADERS).json()["paths"]
    assert {
        path
        for path in paths
        if path not in {"/health", "/ready", "/schemas/report-v3.json"}
    } == {"/v1/market-scans", "/v1/market-scans/latest", "/v1/market-scans/{scan_id}"}


@pytest.mark.parametrize(
    "accept,status",
    [
        ("*/*;q=0", 406),
        ("application/json;q=0.1", 200),
        ("application/json;q=2", 406),
        ("application/json;q=0.1;q=1", 406),
        ('application/json;profile="a,b;c"', 406),
        ('application/json;profile="unfinished', 406),
        ('application/json;charset="utf-8";q=1.000', 200),
        ("application/json;broken", 406),
        ("text/plain;q=1, application/json;q=0.5", 200),
        ("", 406),
    ],
)
def test_accept_weights_and_parameters(accept, status):
    with client() as api:
        response = api.get(
            "/v1/market-scans/latest", headers={**HEADERS, "Accept": accept}
        )
    assert response.status_code == status
    if status == 406:
        assert not response.content


def test_head_errors_are_bodyless_and_keep_status_and_allow():
    with client() as api:
        assert api.head("/v1/market-scans/latest").status_code == 401
        missing = api.head("/v1/market-scans/not-a-uuid", headers=HEADERS)
        unacceptable = api.head(
            "/v1/market-scans/latest", headers={**HEADERS, "Accept": "text/plain"}
        )
    assert missing.status_code == 422 and not missing.content
    assert unacceptable.status_code == 406 and not unacceptable.content


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    "accept,authenticated,status",
    [
        ("application/json", True, 200),
        ("text/plain", True, 406),
        ("text/plain", False, 401),
    ],
)
def test_completion_logs_match_the_wire_response(
    caplog, method, accept, authenticated, status
):
    import logging

    headers = {
        **(HEADERS if authenticated else {}),
        "Accept": accept,
        "X-Request-ID": "completion-test",
    }
    with caplog.at_level(logging.INFO, logger="market_scanner_api"), client() as api:
        response = api.request(method, "/v1/market-scans/latest", headers=headers)
    events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "market_scanner_api"
    ]
    completed = [event for event in events if event["event"] == "http.completed"]
    assert response.status_code == status
    assert len(completed) == 1
    assert completed[0]["status"] == response.status_code
    assert completed[0]["method"] == method
    assert completed[0]["request_id"] == response.headers["X-Request-ID"]
    assert completed[0]["route"] == (
        "/v1/market-scans/latest" if authenticated else "unmatched"
    )
    assert completed[0]["duration_ms"] >= 0
    assert "local-test-token" not in caplog.text
