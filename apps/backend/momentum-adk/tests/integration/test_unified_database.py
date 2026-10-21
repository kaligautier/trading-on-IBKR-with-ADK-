"""One Momentum database, two isolated schemas, existing Scanner untouched."""

import asyncpg
import pytest
from conftest import run_liquibase


@pytest.mark.parametrize(
    "key,own,other,count",
    [
        ("sessions_runtime", "_sessions", "_analysis", 5),
        ("results_runtime", "_analysis", "_sessions", 12),
    ],
)
async def test_schema_isolation_in_one_database(
    unified_database, key, own, other, count
):
    connection = await asyncpg.connect(unified_database[key])
    try:
        assert await connection.fetchval("SELECT current_database()") == "momentum"
        assert await connection.fetchval("SHOW search_path") == f"{own}, pg_catalog"
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM pg_tables WHERE schemaname=$1 "
                "AND tableowner='database_migrator'",
                own,
            )
            == count
        )
        assert await connection.fetchval(
            "SELECT has_schema_privilege(current_user, $1, 'USAGE')", own
        )
        assert not await connection.fetchval(
            "SELECT has_schema_privilege(current_user, $1, 'USAGE')", other
        )
        forbidden_table = "analysis_results" if other == "_analysis" else "sessions"
        for query in (
            f"SELECT * FROM {other}.{forbidden_table}",
            f"CREATE TABLE {own}.forbidden(id INT)",
            "CREATE TEMP TABLE forbidden(id INT)",
            "SET ROLE database_migrator",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(query)
    finally:
        await connection.close()


async def test_unified_migrations_repeat_and_rollback_independently(
    unified_database, migrated_database
):
    admin = await asyncpg.connect(unified_database["admin"])
    legacy = await asyncpg.connect(migrated_database["admin"])
    migrator = unified_database["migrator"]
    options = {"context": None, "changelog": "momentum.yaml"}
    try:
        before = await legacy.fetch(
            "SELECT id,md5sum FROM liquibase.databasechangelog ORDER BY id"
        )
        await admin.execute(
            "INSERT INTO _sessions.sessions VALUES "
            "('momentum','test','retained','{}',NOW(),NOW())"
        )
        run_liquibase(migrator, "update", **options)
        assert (
            await admin.fetchval("SELECT count(*) FROM liquibase.databasechangelog")
            == 3
        )
        run_liquibase(migrator, "rollback-count", "--count=2", **options)
        assert await admin.fetchval("SELECT to_regnamespace('_analysis')") is None
        assert (
            await admin.fetchval(
                "SELECT count(*) FROM _sessions.sessions WHERE id='retained'"
            )
            == 1
        )
        run_liquibase(migrator, "rollback-count", "--count=1", **options)
        assert await admin.fetchval("SELECT to_regnamespace('_sessions')") is None
        assert (
            await legacy.fetch(
                "SELECT id,md5sum FROM liquibase.databasechangelog ORDER BY id"
            )
            == before
        )
    finally:
        run_liquibase(migrator, "update", **options)
        await admin.close()
        await legacy.close()


def test_unified_root_rejects_existing_scanner_database(migrated_database):
    with pytest.raises(RuntimeError, match="(?i)precondition"):
        run_liquibase(
            migrated_database["database_migrator"],
            "update",
            context=None,
            changelog="momentum.yaml",
        )
