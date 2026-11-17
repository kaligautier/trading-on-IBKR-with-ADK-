"""Operational outcomes remain observable without leaking raw exception data."""

import json
import logging
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.postgresql.repository import AnalysisRepository
from app.app_factory import create_app
from app.config.settings import Settings
from app.domain.analyses.errors import StoreUnavailableError
from app.observability import LOGGER


def settings():
    return Settings(
        _env_file=None,
        AUTH_MODE="token",
        DATABASE_POOL_SIZE=1,
        DATABASE_POOL_TIMEOUT=5,
        DATABASE_URL="postgresql://momentum_results_reader:unused@localhost/momentum",
        API_TOKEN="disposable-test-token",
    )


@pytest.mark.parametrize(
    "trace",
    [
        "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
        "invalid",
        "00-" + "0" * 32 + "-1234567890abcdef-01",
    ],
)
async def test_request_logs_are_json_with_validated_trace_context(trace, caplog):
    with caplog.at_level(logging.INFO, logger="momentum_api"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(settings())),
            base_url="http://test",
        ) as client:
            response = await client.get("/health", headers={"traceparent": trace})
    event = json.loads(caplog.records[-1].getMessage())
    assert event["event"] == "request_completed"
    assert event["request_id"] == response.headers["request-id"]
    assert event["status"] == 200 and event["category"] == "SUCCESS"
    assert event["severity"] == "INFO" and event["duration_ms"] >= 0
    if trace.startswith("00-1234"):
        assert event["trace_id"] == "1234567890abcdef1234567890abcdef"
        assert event["parent_span_id"] == "1234567890abcdef"
    else:
        assert "trace_id" not in event


async def test_store_failure_preserves_cause_without_exposing_its_message():
    original = OSError("private database connection details")
    engine = MagicMock(spec=AsyncEngine)
    engine.connect.side_effect = original
    with pytest.raises(StoreUnavailableError) as caught:
        async with AnalysisRepository(engine).read():
            pytest.fail("Connection should fail before yielding")
    assert caught.value.__cause__ is original
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("path, expected", [("/health", 200), ("/missing", 404)])
async def test_logging_failure_does_not_replace_http_outcome(
    monkeypatch, path, expected
):
    # A synchronous logging handler can fail; no coroutine should be introduced.
    def broken_logger(*args, **kwargs):
        raise RuntimeError("private logging failure")

    monkeypatch.setattr(LOGGER, "log", broken_logger)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings())),
        base_url="http://test",
    ) as client:
        response = await client.get(
            path, headers={"Authorization": "Bearer disposable-test-token"}
        )
    assert response.status_code == expected
    assert "logging failure" not in response.text
