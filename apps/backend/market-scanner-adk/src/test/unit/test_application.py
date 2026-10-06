import logging

import pytest
from fastapi.testclient import TestClient

from app.application import ScannerRouteAuthorizer, _requires_token, create_app
from app.utils.error import (
    InvalidInputError,
    MarketDataCollectionError,
    MarketDataUnavailableError,
)


def should_accept_the_dedicated_scanner_token() -> None:
    authorizer = ScannerRouteAuthorizer("scanner-secret")

    assert authorizer.is_authorized({"X-Market-Scanner-Token": "scanner-secret"})


def should_keep_bearer_token_compatibility() -> None:
    authorizer = ScannerRouteAuthorizer("scanner-secret")

    assert authorizer.is_authorized({"Authorization": "Bearer scanner-secret"})


def should_reject_an_invalid_scanner_token() -> None:
    authorizer = ScannerRouteAuthorizer("scanner-secret")

    assert not authorizer.is_authorized({"X-Market-Scanner-Token": "wrong"})


def should_leave_routes_open_when_no_token_is_configured() -> None:
    authorizer = ScannerRouteAuthorizer("")

    assert authorizer.is_authorized({})


def should_protect_every_route_except_health() -> None:
    assert _requires_token("/run")
    assert _requires_token("/run_sse")
    assert _requires_token("/apps/market_scanner/users/user/sessions")
    assert not _requires_token("/health")


@pytest.mark.parametrize(
    ("allowed_origins", "origin", "expected_status"),
    [
        (["http://127.0.0.1:8080"], "http://127.0.0.1:8080", 200),
        (["http://127.0.0.1:8080"], "https://untrusted.example", 403),
        ([], "http://127.0.0.1:8080", 403),
    ],
)
def should_enforce_explicit_browser_origins(
    monkeypatch, allowed_origins, origin, expected_status
):
    monkeypatch.setattr("app.application.settings.ADK_ALLOW_ORIGINS", allowed_origins)
    app = create_app()

    @app.post("/origin-check")
    async def origin_check():
        return {"ok": True}

    client = TestClient(app, base_url="https://scanner.example.run.app")
    response = client.post("/origin-check", headers={"Origin": origin})
    assert response.status_code == expected_status


def should_close_the_database_pool_on_application_shutdown(monkeypatch):
    from unittest.mock import AsyncMock

    close = AsyncMock()
    monkeypatch.setattr("app.application.close_database", close)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        close.assert_not_awaited()
    close.assert_awaited_once()


def should_emit_one_canonical_event_for_an_http_request(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = TestClient(create_app()).get(
            "/health", headers={"X-Request-ID": "health-request"}
        )

    events = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http.request"
    ]
    assert response.status_code == 200
    assert len(events) == 1
    assert events[0].__dict__["request_id"] == "health-request"


@pytest.mark.parametrize(
    ("error_type", "status_code", "code"),
    [
        (InvalidInputError, 400, "INVALID_INPUT"),
        (MarketDataCollectionError, 502, "MARKET_DATA_COLLECTION_ERROR"),
        (MarketDataUnavailableError, 503, "MARKET_DATA_UNAVAILABLE"),
    ],
)
def should_map_app_errors_and_record_their_codes(error_type, status_code, code, caplog):
    app = create_app()

    @app.get("/test-error")
    async def fail():
        raise error_type("Test failure", details={"symbol": "^GSPC"})

    with caplog.at_level(logging.INFO, logger="app.request"):
        response = TestClient(app).get("/test-error")

    assert response.status_code == status_code
    assert response.json() == {"error": "Test failure"}
    assert response.headers["x-request-id"]
    events = [r for r in caplog.records if getattr(r, "event", None) == "http.request"]
    assert len(events) == 1
    assert events[0].__dict__["error.code"] == code
    assert events[0].__dict__["error.details"] == {"symbol": "^GSPC"}
    assert events[0].__dict__["outcome"] != "success"


@pytest.mark.parametrize(
    "path",
    [
        "/list-apps",
        "/dev/apps/market_scanner/debug/trace/session/private-session",
        "/config/telemetry",
        "/builder/save",
        "/agent-identity/finalize",
    ],
)
def should_protect_adk_administration_routes(monkeypatch, path):
    monkeypatch.setattr("app.application.settings.MARKET_SCANNER_TOKEN", "test-token")
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 401
        assert client.post(path, json={}).status_code == 401
        assert client.get("/health").status_code == 200
        assert (
            client.get(
                "/list-apps", headers={"X-Market-Scanner-Token": "test-token"}
            ).status_code
            == 200
        )


def should_protect_websocket_execution(monkeypatch):
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr("app.application.settings.MARKET_SCANNER_TOKEN", "test-token")
    with TestClient(create_app()) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/run_live"):
                pass
    assert rejected.value.code == 1008
