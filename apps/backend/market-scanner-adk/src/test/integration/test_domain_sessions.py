"""Persistent Scanner sessions and reports on the owned local domain database."""

import os
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from google.adk.events import Event, EventActions

from app import application
from app.config.settings import settings
from app.services.database import close_database
from app.services.market_scan_persistence import MarketScanPersistence
from app.services.session_database import ScannerSessionService
from test.unit.services.test_market_scan_persistence import _regime

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOMAIN_TESTS") != "1", reason="Run the local domain rehearsal"
)

PORT = os.getenv("SCANNER_DOMAIN_TEST_PORT", "55471")
WRITER = (
    f"postgresql://market_scanner_writer:domain-test-only@127.0.0.1:{PORT}/market_scanner"
)
READER = WRITER.replace("market_scanner_writer:", "market_scanner_reader:")


@pytest.fixture
async def domain_store(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", WRITER)
    monkeypatch.setattr(settings, "DATABASE_SCHEMA", "_analysis")
    monkeypatch.setattr(settings, "MARKET_SCANNER_TOKEN", "local-test-token")
    await close_database()
    yield
    await close_database()


async def test_durable_session_and_analysis_have_independent_lifecycles(domain_store):
    session_id = uuid4().hex
    async with ScannerSessionService(WRITER) as service:
        session = await service.create_session(
            app_name="market_scanner", user_id="test", session_id=session_id
        )
        await service.append_event(
            session,
            Event(
                author="agent",
                invocation_id="test",
                actions=EventActions(state_delta={"proof": {"stored": True}}),
            ),
        )
        await MarketScanPersistence().save(_regime(), session_id)
    await close_database()
    async with ScannerSessionService(WRITER) as reopened:
        loaded = await reopened.get_session(
            app_name="market_scanner", user_id="test", session_id=session_id
        )
        assert loaded.state["proof"]["stored"] is True
        assert len(loaded.events) == 1
        await reopened.delete_session(
            app_name="market_scanner", user_id="test", session_id=session_id
        )
    reader = await asyncpg.connect(READER)
    try:
        report = await reader.fetchrow(
            "SELECT report, session_id FROM _analysis.market_scans WHERE session_id=$1",
            session_id,
        )
        assert report and report["session_id"] == session_id
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await reader.fetch("SELECT * FROM _sessions.sessions")
    finally:
        await reader.close()


async def test_adk_http_session_survives_application_recreation(domain_store):
    session_id = uuid4().hex
    path = f"/apps/market_scanner/users/test/sessions/{session_id}"
    headers = {"X-Market-Scanner-Token": "local-test-token"}
    with TestClient(application.create_app()) as client:
        assert client.post(path, headers=headers, json={"proof": 42}).status_code == 200
        assert client.get(path).status_code == 401
    with TestClient(application.create_app()) as restarted:
        response = restarted.get(path, headers=headers)
        assert response.status_code == 200
        assert response.json()["state"]["proof"] == 42


async def test_wrong_or_unmigrated_database_fails_without_sdk_ddl():
    url = WRITER.replace("market_scanner_writer", "postgres").replace(
        "/market_scanner", "/postgres"
    )
    service = ScannerSessionService(url)
    try:
        with pytest.raises(RuntimeError, match="session migrations"):
            await service.prepare_tables()
    finally:
        await service.close()
    admin = await asyncpg.connect(url)
    try:
        assert await admin.fetchval("SELECT to_regnamespace('_sessions')") is None
        assert await admin.fetchval("SELECT to_regclass('public.sessions')") is None
    finally:
        await admin.close()
