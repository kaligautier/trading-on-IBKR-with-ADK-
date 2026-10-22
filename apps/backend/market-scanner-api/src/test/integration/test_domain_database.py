"""Read the Scanner-written report across independent reader application lifetimes."""

import os

import asyncpg
import httpx
import pytest

from app.application import create_app
from app.config.settings import Settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOMAIN_TESTS") != "1", reason="Run the local domain rehearsal"
)
URL = (
    "postgresql://market_scanner_reader:domain-test-only@127.0.0.1:55461/market_scanner"
)


async def test_reader_restart_and_session_isolation():
    configuration = Settings(
        DATABASE_URL=URL, API_TOKEN="integration-test-token", _env_file=None
    )
    first = None
    for _ in range(2):
        application = create_app(configuration)
        async with (
            application.router.lifespan_context(application),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url="http://test"
            ) as client,
        ):
            assert (await client.get("/market-scans/latest")).status_code == 401
            response = await client.get(
                "/market-scans/latest",
                headers={"Authorization": "Bearer integration-test-token"},
            )
            assert response.status_code == 200
            report = response.json()
            assert report["report"]["schema_version"] == 3
            assert "session_id" not in report
            if first is None:
                first = report
            else:
                assert report == first
    connection = await asyncpg.connect(URL)
    try:
        for statement in (
            "SELECT * FROM _sessions.sessions",
            "SELECT * FROM _sessions.events",
            "DELETE FROM _analysis.market_scans",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
    finally:
        await connection.close()
