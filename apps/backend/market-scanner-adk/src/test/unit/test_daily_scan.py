"""Run the scheduled HTTP route through real ADK, stubbing only external work."""

import json
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from google.adk import Workflow
from google.adk.models import LlmResponse
from google.adk.models.google_llm import Gemini
from google.genai import types

from app import application
from app.components.agents.market_scanner import agent as scanner
from app.jobs import daily_scan
from test.unit.components.agents.test_regime_workflow import conclusion, market_data


@pytest.fixture
def scheduled_workflow(monkeypatch):
    data = market_data()
    calls = []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        text = "Research context." if len(calls) % 2 else json.dumps(conclusion(data))
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        )

    save = AsyncMock()
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "test-token")
    monkeypatch.setattr(application.settings, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    return save


async def should_run_the_workflow_and_persist_with_a_unique_session_per_request(
    scheduled_workflow,
):
    results = [await daily_scan.run_scan() for _ in range(2)]
    assert results[0]["session_id"] != results[1]["session_id"]
    assert scheduled_workflow.await_count == 2
    for result, call in zip(results, scheduled_workflow.await_args_list, strict=True):
        UUID(result["session_id"])
        assert result["marker"] == "scheduled:" + result["session_id"]
        assert result["assets"] == 25
        assert call.args[1] == result["marker"]
        assert len(call.args[0].assets) == 25


def should_accept_dispatch_without_running_the_workflow(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "test-token")
    job = "projects/test-project/locations/europe-west1/jobs/market-scanner-daily"
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_JOB", job)
    dispatch = Mock(
        return_value="projects/test-project/locations/europe-west1/operations/op1"
    )
    monkeypatch.setattr(application, "dispatch_scan", dispatch)
    with TestClient(application.create_app()) as client:
        assert client.post("/internal/daily-scan").status_code == 401
        dispatch.assert_not_called()
        response = client.post(
            "/internal/daily-scan", headers={"X-Market-Scanner-Token": "test-token"}
        )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "operation": dispatch.return_value}
    dispatch.assert_called_once_with(job)


def should_report_dispatch_failure_without_exposing_details(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "")
    monkeypatch.setattr(
        application.settings,
        "MARKET_SCANNER_JOB",
        "projects/test-project/locations/europe-west1/jobs/scanner",
    )
    monkeypatch.setattr(
        application, "dispatch_scan", Mock(side_effect=RuntimeError("private details"))
    )
    with TestClient(application.create_app()) as client:
        response = client.post("/internal/daily-scan")
    assert response.status_code == 502
    assert response.json() == {"detail": "Scheduled scan dispatch failed"}


async def should_fail_the_worker_when_persistence_fails(scheduled_workflow):
    scheduled_workflow.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError, match="ADK workflow failed"):
        await daily_scan.run_scan()


async def should_reject_a_workflow_that_ends_before_persistence(
    scheduled_workflow, monkeypatch
):
    monkeypatch.setattr(
        daily_scan,
        "root_agent",
        Workflow(name="market_scanner", edges=[("START", scanner.get_market_data)]),
    )
    with pytest.raises(RuntimeError, match="without a persisted report"):
        await daily_scan.run_scan()
    scheduled_workflow.assert_not_awaited()


def should_reject_dispatch_without_a_configured_job(monkeypatch):
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "")
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_JOB", "")
    dispatch = Mock()
    monkeypatch.setattr(application, "dispatch_scan", dispatch)
    with TestClient(application.create_app()) as client:
        response = client.post("/internal/daily-scan")
    assert response.status_code == 503
    dispatch.assert_not_called()


async def should_fail_the_worker_without_a_database(scheduled_workflow, monkeypatch):
    monkeypatch.setattr(application.settings, "DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="Database persistence"):
        await daily_scan.run_scan()
    scheduled_workflow.assert_not_awaited()


async def should_use_execution_name_to_correlate_the_persisted_report(
    scheduled_workflow, monkeypatch
):
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "market-scanner-daily-abcde")
    result = await daily_scan.run_scan()
    assert result["marker"] == "scheduled:market-scanner-daily-abcde"
    assert scheduled_workflow.await_args.args[1] == result["marker"]


@pytest.mark.parametrize("failed", [False, True])
async def should_exit_with_worker_status_and_close_database(monkeypatch, failed):
    run = AsyncMock(return_value={"assets": 25})
    if failed:
        run.side_effect = RuntimeError("failed")
    close = AsyncMock()
    monkeypatch.setattr(daily_scan, "run_scan", run)
    monkeypatch.setattr(daily_scan, "close_database", close)
    assert await daily_scan.main() == int(failed)
    close.assert_awaited_once()
