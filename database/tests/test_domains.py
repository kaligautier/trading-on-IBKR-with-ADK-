"""Real fresh migrations, database isolation and durable ADK state."""

import subprocess
from pathlib import Path

import asyncpg
import pytest
from google.adk.events import Event, EventActions
from google.adk.sessions import DatabaseSessionService

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "domain-test-only"


def url(domain, role):
    return f"postgresql://{role}:{PASSWORD}@127.0.0.1:55461/{domain}"


@pytest.fixture(scope="module", autouse=True)
def databases():
    subprocess.run(
        ["python3", str(ROOT / "database/scripts/local_domains.py"), "reset"],
        check=True,
    )


@pytest.mark.parametrize("domain", ["market_scanner", "momentum"])
async def test_sessions_survive_restart_and_domain_access_is_denied(domain):
    role = (
        "market_scanner_writer"
        if domain == "market_scanner"
        else "momentum_sessions_writer"
    )
    kwargs = {
        "pool_size": 1,
        "max_overflow": 0,
        "connect_args": {"server_settings": {"search_path": "_sessions, pg_catalog"}},
    }
    address = url(domain, role).replace("postgresql://", "postgresql+asyncpg://")
    first = DatabaseSessionService(address, **kwargs)
    try:
        session = await first.create_session(
            app_name=domain, user_id="local-test", session_id="restart-proof"
        )
        await first.append_event(
            session,
            Event(
                author="agent",
                invocation_id="local-invocation",
                actions=EventActions(state_delta={"persisted": {"value": 42}}),
            ),
        )
    finally:
        await first.close()
    second = DatabaseSessionService(address, **kwargs)
    try:
        loaded = await second.get_session(
            app_name=domain, user_id="local-test", session_id="restart-proof"
        )
        assert loaded.state["persisted"] == {"value": 42}
        assert len(loaded.events) == 1
        assert second.db_engine.pool.size() == 1
    finally:
        await second.close()
    runtime = await asyncpg.connect(url(domain, role))
    try:
        for statement in (
            "CREATE TABLE _sessions.forbidden(id int)",
            "UPDATE _sessions.adk_internal_metadata SET value='0'",
            "SELECT * FROM liquibase.databasechangelog",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute(statement)
    finally:
        await runtime.close()
    other = "momentum" if domain == "market_scanner" else "market_scanner"
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await asyncpg.connect(url(other, role))


async def test_reader_cannot_access_sessions_and_chains_are_independent():
    reader = await asyncpg.connect(url("market_scanner", "market_scanner_reader"))
    try:
        assert await reader.fetchval("SELECT count(*) FROM _analysis.market_scans") == 0
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await reader.fetch("SELECT * FROM _sessions.sessions")
    finally:
        await reader.close()
    for domain, expected in (("market_scanner", 2), ("momentum", 2)):
        migrator = await asyncpg.connect(url(domain, "database_migrator"))
        try:
            assert (
                await migrator.fetchval(
                    "SELECT count(*) FROM liquibase.databasechangelog"
                )
                == expected
            )
            schemas = await migrator.fetch(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name IN ('_analysis', '_sessions', 'liquibase')"
            )
            assert len(schemas) == 3
        finally:
            await migrator.close()
