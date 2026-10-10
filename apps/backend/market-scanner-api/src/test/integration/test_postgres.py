"""Required PostgreSQL coverage. Only a disposable local test database is accepted."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.application import create_app
from app.config.settings import Settings
from app.database import create_engine

ROOT = Path(__file__).resolve().parents[6]
REPORT = json.loads(
    (ROOT / "apps/backend/market-scanner-adk/examples/report-v3.json").read_text()
)["market_regime"]
HEADERS = {"Authorization": "Bearer integration-test-token"}


@pytest.fixture
async def database():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.fail("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost", "::1"} or not url.database.endswith(
        "_test"
    ):
        pytest.fail("Use a disposable localhost database with a name ending in _test")
    admin = await asyncpg.connect(raw)
    try:
        for role in [
            "database_migrator",
            "market_scanner_writer",
            "market_scanner_reader",
        ]:
            if not await admin.fetchval(
                "SELECT 1 FROM pg_roles WHERE rolname=$1", role
            ):
                await admin.execute(
                    f"CREATE ROLE {role} LOGIN PASSWORD 'integration-only'"
                )
        await admin.execute("DROP SCHEMA IF EXISTS market_scanner CASCADE")
        # Apply the same checked-in DDL and grants as the Liquibase changeset.
        await admin.execute(
            (ROOT / "database/changelog/market-scanner/001-initial.sql").read_text()
        )
        reader = url.set(username="market_scanner_reader", password="integration-only")
        settings = Settings(
            DATABASE_URL=reader.render_as_string(hide_password=False),
            API_TOKEN="integration-test-token",
            _env_file=None,
        )
        yield admin, settings
    finally:
        await admin.close()


async def insert(admin, number, *, timestamp=None, report=REPORT):
    await admin.execute(
        "INSERT INTO market_scanner.market_scans "
        "(id, scan_date, session_id, regime, summary, report, created_at) "
        "VALUES ($1, '2026-10-05', 'private-session', 'cautious', 'Summary', $2, $3)",
        UUID(int=number),
        json.dumps(report),
        timestamp or datetime(2026, 10, 5, tzinfo=UTC),
    )


async def test_reader_pagination_detail_and_concurrent_insert(database):
    admin, settings = database
    for number in range(1, 6):
        await insert(admin, number)
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
            headers=HEADERS,
        ) as client:
            latest = await client.get("/market-scans/latest")
            assert latest.status_code == 200
            assert latest.json()["id"] == str(UUID(int=5))
            assert latest.json()["report"] == REPORT
            first = (await client.get("/market-scans", params={"page_size": 2})).json()
            assert first["next_page_token"]
            ids = [row["id"] for row in first["items"]]
            # A newly committed latest scan must not shift the ongoing history.
            await insert(admin, 6)
            token = first["next_page_token"]
            while token:
                page = (
                    await client.get(
                        "/market-scans", params={"page_size": 2, "page_token": token}
                    )
                ).json()
                ids.extend(row["id"] for row in page["items"])
                token = page["next_page_token"]
            assert ids == [str(UUID(int=n)) for n in range(5, 0, -1)]
            detail = await client.get(f"/market-scans/{UUID(int=1)}")
            assert detail.json()["report"] == REPORT
            assert "session_id" not in detail.text
            assert (await client.get("/ready")).status_code == 200
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SHOW transaction_read_only"))
            ).scalar() == "on"
            assert not (
                await connection.execute(
                    text(
                        "SELECT has_table_privilege(current_user, "
                        "'market_scanner.market_scans', 'INSERT')"
                    )
                )
            ).scalar()
            with pytest.raises(DBAPIError):
                await connection.execute(
                    text("DELETE FROM market_scanner.market_scans")
                )
    finally:
        await engine.dispose()


async def test_empty_store_invalid_report_and_unavailable_schema(database):
    admin, settings = database
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
            headers=HEADERS,
        ) as client:
            assert (await client.get("/market-scans/latest")).status_code == 404
            assert (await client.get("/market-scans")).json() == {
                "items": [],
                "next_page_token": "",
            }
            await insert(admin, 1, report=None)
            assert (await client.get("/market-scans/latest")).status_code == 500
            await admin.execute("DROP SCHEMA market_scanner CASCADE")
            response = await client.get("/market-scans/latest")
            assert response.status_code == 503
            assert "integration-only" not in response.text


async def test_other_schema_cannot_supply_a_report(database):
    admin, settings = database
    await admin.execute("CREATE TABLE public.market_scans (id UUID)")
    try:
        await admin.execute(
            "GRANT SELECT ON public.market_scans TO market_scanner_reader"
        )
        application = create_app(settings)
        async with application.router.lifespan_context(application):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://test",
                headers=HEADERS,
            ) as client:
                assert (await client.get("/market-scans/latest")).status_code == 404
    finally:
        await admin.execute("DROP TABLE public.market_scans")
