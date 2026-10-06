"""Exercise the two-call ADK contract used by the direct Scheduler endpoint."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app import application
from app.jobs.scheduled_scan import ScheduledScanError, run_scheduled_scan


async def should_store_the_persistence_marker_in_real_adk_session_state(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "")
    app_transport = httpx.ASGITransport(app=application.create_app())

    async def respond(request):
        if request.url.path == "/run_sse":
            return httpx.Response(
                200,
                text=(
                    'data: {"nodeInfo":{"path":"root/persist_market_scan"},'
                    '"output":{"market_regime":{"assets":[{}]}}}\n\n'
                ),
            )
        return await app_transport.handle_async_request(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="http://localhost"
    ) as client:
        result = await run_scheduled_scan(client, {})
        session = await client.get(
            "/apps/market_scanner/users/scheduler/sessions/" + result["session_id"]
        )
    assert session.json()["state"].get("session_id") == result["marker"]


async def should_use_one_uuid_for_session_and_execution_and_require_persistence():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/sessions"):
            session_id = json.loads(request.content)["session_id"]
            return httpx.Response(200, json={"id": session_id})
        body = json.loads(request.content)
        assert body["sessionId"] == json.loads(requests[0].content)["session_id"]
        data = json.dumps(
            {
                "nodeInfo": {"path": "root/persist_market_scan"},
                "output": {"market_regime": {"assets": [{"symbol": "SPY"}]}},
            }
        )
        return httpx.Response(200, text="data: " + data + "\n\n")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="http://adk-internal"
    ) as client:
        result = await run_scheduled_scan(client, {})
    UUID(result["session_id"])
    assert result["marker"] == "scheduled:" + result["session_id"]
    assert result["assets"] == 1
    assert len(requests) == 2
    assert json.loads(requests[0].content)["state"]["session_id"] == result["marker"]


async def should_reject_an_sse_stream_without_persistence():
    def respond(request):
        if request.url.path.endswith("/sessions"):
            return httpx.Response(
                200, json={"id": json.loads(request.content)["session_id"]}
            )
        return httpx.Response(
            200, text='data: {"nodeInfo":{"path":"root/assemble_market_data"}}\n\n'
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="http://adk-internal"
    ) as client:
        with pytest.raises(ScheduledScanError, match="without a persisted report"):
            await run_scheduled_scan(client, {})


def should_protect_the_scheduler_endpoint_and_report_scan_failure(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "test-token")
    monkeypatch.setattr(application.settings, "DATABASE_URL", "postgresql://test")
    failed = AsyncMock(side_effect=ScheduledScanError("private provider details"))
    monkeypatch.setattr(application, "run_scheduled_scan", failed)
    with TestClient(application.create_app()) as client:
        assert client.post("/internal/daily-scan").status_code == 401
        response = client.post(
            "/internal/daily-scan", headers={"X-Market-Scanner-Token": "test-token"}
        )
    assert response.status_code == 502
    assert "private provider details" not in response.text


def should_reject_scheduled_scans_without_database_configuration(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "")
    monkeypatch.setattr(application.settings, "DATABASE_URL", "")
    run = AsyncMock()
    monkeypatch.setattr(application, "run_scheduled_scan", run)
    with TestClient(application.create_app()) as client:
        response = client.post("/internal/daily-scan")
    assert response.status_code == 503
    run.assert_not_awaited()
