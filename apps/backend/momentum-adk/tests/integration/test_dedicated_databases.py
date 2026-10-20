"""Two databases on one service, with independent migration/runtime access."""

from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from conftest import DATABASE, run_liquibase
from google.adk.events import Event, EventActions

from app.infrastructure.session_database import create_session_service


@pytest.mark.parametrize(
    "source,target",
    [
        ("momentum_sessions", "momentum_results"),
        ("momentum_results", "momentum_sessions"),
    ],
)
async def test_runtime_cannot_connect_to_other_database(
    dedicated_databases, source, target
):
    url = urlsplit(dedicated_databases[source]["runtime"])
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        connection = await asyncpg.connect(urlunsplit(url._replace(path="/" + target)))
        await connection.close()


@pytest.mark.parametrize("name", ["momentum_sessions", "momentum_results"])
async def test_new_runtime_roles_cannot_read_existing_scanner(
    dedicated_databases, migrated_database, name
):
    runtime = urlsplit(dedicated_databases[name]["runtime"])
    legacy = urlsplit(migrated_database["admin"])
    connection = await asyncpg.connect(urlunsplit(runtime._replace(path=legacy.path)))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.fetch("SELECT * FROM market_scanner.market_scans")
    finally:
        await connection.close()


@pytest.mark.parametrize("name", ["momentum_sessions", "momentum_results"])
async def test_dedicated_roles_are_bounded_and_cannot_create_objects(
    dedicated_databases, name
):
    connection = await asyncpg.connect(dedicated_databases[name]["runtime"])
    try:
        assert await connection.fetchval("SELECT current_database()") == name
        assert await connection.fetchval("SHOW search_path") == "momentum, pg_catalog"
        assert (
            await connection.fetchval(
                "SELECT rolconnlimit FROM pg_roles WHERE rolname=current_user"
            )
            == 2
        )
        for query in (
            "CREATE TEMP TABLE forbidden(id INT)",
            "CREATE TABLE public.forbidden(id INT)",
            "CREATE SCHEMA forbidden",
            "SET ROLE database_migrator",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(query)
    finally:
        await connection.close()


async def test_adk_persists_only_in_dedicated_sessions_database(
    dedicated_databases, migrated_database
):
    url = dedicated_databases["momentum_sessions"]["runtime"]
    service = await create_session_service(url)
    try:
        session = await service.create_session(
            app_name="momentum",
            user_id="split-db-test",
            session_id="separate-session",
            state={"ticker": "NVDA"},
        )
        await service.append_event(
            session,
            Event(
                author="analyst",
                invocation_id="separate-invocation",
                actions=EventActions(state_delta={"stage": "research"}),
            ),
        )
    finally:
        await service.close()
    service = await create_session_service(url)
    try:
        restored = await service.get_session(
            app_name="momentum",
            user_id="split-db-test",
            session_id="separate-session",
        )
        assert restored.state == {"ticker": "NVDA", "stage": "research"}
        assert restored.events[0].invocation_id == "separate-invocation"
        for target in (
            migrated_database["admin"],
            dedicated_databases["momentum_results"]["admin"],
        ):
            connection = await asyncpg.connect(target)
            try:
                if target == migrated_database["admin"]:
                    assert (
                        await connection.fetchval(
                            "SELECT count(*) FROM momentum.sessions "
                            "WHERE id='separate-session'"
                        )
                        == 0
                    )
                else:
                    assert (
                        await connection.fetchval(
                            "SELECT to_regclass('momentum.sessions')"
                        )
                        is None
                    )
            finally:
                await connection.close()
        await service.delete_session(
            app_name="momentum", user_id="split-db-test", session_id="separate-session"
        )
    finally:
        await service.close()


async def test_bootstrap_refuses_existing_application_database(migrated_database):
    connection = await asyncpg.connect(migrated_database["admin"])
    try:
        with pytest.raises(asyncpg.RaiseError, match="dedicated Momentum database"):
            await connection.execute(
                (DATABASE / "momentum-databases-bootstrap.sql").read_text()
            )
    finally:
        await connection.execute("ROLLBACK")
        await connection.close()


async def test_dedicated_session_migrations_repeat_and_rollback(
    dedicated_databases, migrated_database
):
    legacy = await asyncpg.connect(migrated_database["admin"])
    session_admin = await asyncpg.connect(
        dedicated_databases["momentum_sessions"]["admin"]
    )
    migrator = dedicated_databases["momentum_sessions"]["migrator"]
    try:
        before = await legacy.fetch(
            "SELECT id, md5sum FROM liquibase.databasechangelog ORDER BY id"
        )
        run_liquibase(
            migrator, "update", context=None, changelog="momentum-sessions.yaml"
        )
        assert (
            await session_admin.fetchval(
                "SELECT count(*) FROM liquibase.databasechangelog"
            )
            == 1
        )
        assert (
            await session_admin.fetchval(
                "SELECT to_regclass('market_scanner.market_scans')"
            )
            is None
        )
        run_liquibase(
            migrator,
            "rollback-count",
            "--count=1",
            context=None,
            changelog="momentum-sessions.yaml",
        )
        assert (
            await session_admin.fetchval("SELECT to_regnamespace('momentum')") is None
        )
        assert (
            await legacy.fetch(
                "SELECT id, md5sum FROM liquibase.databasechangelog ORDER BY id"
            )
            == before
        )
    finally:
        run_liquibase(
            migrator, "update", context=None, changelog="momentum-sessions.yaml"
        )
        await session_admin.close()
        await legacy.close()


def test_session_changelog_rejects_legacy_database(migrated_database):
    with pytest.raises(RuntimeError, match="(?i)precondition"):
        run_liquibase(
            migrated_database["database_migrator"],
            "update",
            context=None,
            changelog="momentum-sessions.yaml",
        )
