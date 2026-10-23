"""Busy work is rejected before the handler; authentication still runs first."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.application import create_app
from app.services.admission import ScannerBusyError


def should_reject_busy_work_before_handler_and_preserve_auth(monkeypatch):
    @asynccontextmanager
    async def busy():
        raise ScannerBusyError()
        yield  # pragma: no cover

    monkeypatch.setattr("app.middleware.admission.admit_scan", busy)
    monkeypatch.setattr("app.application.settings.MARKET_SCANNER_TOKEN", "test-token")
    app = create_app()
    expensive = AsyncMock()

    @app.post("/test-analysis")
    async def analyze():
        await expensive()
        return {}

    client = TestClient(app)
    assert client.post("/test-analysis").status_code == 401
    response = client.post(
        "/test-analysis", headers={"X-Market-Scanner-Token": "test-token"}
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert response.json() == {"detail": "Scanner execution capacity is busy"}
    assert client.get("/health").status_code == 200
    expensive.assert_not_awaited()


async def should_exit_busy_job_without_starting_session_or_model(monkeypatch):
    from app.jobs import daily_scan

    @asynccontextmanager
    async def busy():
        raise ScannerBusyError()
        yield  # pragma: no cover

    monkeypatch.setattr(daily_scan, "admit_scan", busy)
    monkeypatch.setattr(daily_scan.settings, "DATABASE_URL", "postgres://test")
    session = AsyncMock()
    monkeypatch.setattr(daily_scan, "ScannerSessionService", session)
    assert await daily_scan.main() == 75
    session.assert_not_called()
