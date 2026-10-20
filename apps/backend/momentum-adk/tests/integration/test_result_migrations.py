"""Liquibase owns result tables; the runtime can only insert and read results."""

import asyncpg
import pytest
from conftest import run_liquibase
from sqlalchemy import Float, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.models import Base


async def test_migrated_result_schema_matches_orm(unified_database):
    engine = create_async_engine(
        unified_database["admin"].replace("postgresql://", "postgresql+asyncpg://"),
        pool_size=1,
        max_overflow=0,
    )

    def compare(connection):
        inspector = inspect(connection)
        for table in Base.metadata.sorted_tables:
            actual = {
                c["name"]: c for c in inspector.get_columns(table.name, "_analysis")
            }
            assert set(actual) == set(table.c.keys())
            for column in table.c:
                reflected = actual[column.name]
                assert reflected["nullable"] == column.nullable
                if isinstance(column.type, Float):
                    assert isinstance(reflected["type"], Float)
                else:
                    assert reflected["type"].compile(
                        dialect=postgresql.dialect()
                    ) == column.type.compile(dialect=postgresql.dialect())
                assert reflected["default"] is None
            assert inspector.get_pk_constraint(table.name, "_analysis")[
                "constrained_columns"
            ] == list(table.primary_key.columns.keys())
            assert not inspector.get_unique_constraints(table.name, "_analysis")
            assert {
                (i["name"], tuple(i["column_names"]), i["unique"])
                for i in inspector.get_indexes(table.name, "_analysis")
            } == {(i.name, tuple(i.columns.keys()), i.unique) for i in table.indexes}
            foreign_keys = inspector.get_foreign_keys(table.name, "_analysis")
            assert len(foreign_keys) == len(table.foreign_keys)
            for key in foreign_keys:
                assert key["constrained_columns"] == ["result_id"]
                assert key["referred_schema"] == "_analysis"
                assert key["referred_table"] == "analysis_results"
                assert key["referred_columns"] == ["id"]

    try:
        async with engine.connect() as connection:
            await connection.run_sync(compare)
    finally:
        await engine.dispose()


async def test_result_tables_have_only_explicit_runtime_grants(unified_database):
    admin = await asyncpg.connect(unified_database["admin"])
    try:
        for table in Base.metadata.sorted_tables:
            assert (
                await admin.fetchval(
                    "SELECT tableowner FROM pg_tables WHERE schemaname='_analysis' "
                    "AND tablename=$1",
                    table.name,
                )
                == "database_migrator"
            )
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            ):
                allowed = await admin.fetchval(
                    "SELECT has_table_privilege('momentum_results_writer', $1, $2)",
                    table.fullname,
                    privilege,
                )
                assert allowed is (privilege in {"SELECT", "INSERT"})
                assert not await admin.fetchval(
                    "SELECT has_table_privilege('market_scanner_writer', $1, $2)",
                    table.fullname,
                    privilege,
                )
    finally:
        await admin.close()


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE _analysis.analysis_results SET ticker='forbidden'",
        "DELETE FROM _analysis.analysis_results",
        "TRUNCATE _analysis.analysis_results CASCADE",
        "ALTER TABLE _analysis.analysis_results ADD COLUMN forbidden INT",
        "DROP TABLE _analysis.analysis_results CASCADE",
    ],
)
async def test_runtime_cannot_modify_completed_results(unified_database, query):
    writer = await asyncpg.connect(unified_database["results_runtime"])
    transaction = writer.transaction()
    await transaction.start()
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await writer.execute(query)
    finally:
        await transaction.rollback()
        await writer.close()


async def test_result_rollback_preserves_other_databases(
    unified_database, migrated_database
):
    admin = await asyncpg.connect(unified_database["admin"])
    sessions = await asyncpg.connect(unified_database["admin"])
    scanner = await asyncpg.connect(migrated_database["admin"])
    migrator = unified_database["migrator"]
    options = {"context": None, "changelog": "momentum.yaml"}
    try:
        await sessions.execute(
            "INSERT INTO _sessions.sessions VALUES "
            "('momentum','migration-test','retained-session','{}',NOW(),NOW())"
        )
        before = await scanner.fetch(
            "SELECT id, md5sum FROM liquibase.databasechangelog ORDER BY id"
        )
        rows = await scanner.fetchval(
            "SELECT jsonb_agg(to_jsonb(s)) FROM market_scanner.market_scans s"
        )
        run_liquibase(migrator, "update", **options)
        assert (
            await admin.fetchval("SELECT count(*) FROM liquibase.databasechangelog")
            == 2
        )
        assert await admin.fetchval("SELECT to_regclass('_analysis.sessions')") is None
        assert (
            await admin.fetchval("SELECT to_regclass('market_scanner.market_scans')")
            is None
        )
        run_liquibase(migrator, "rollback-count", "--count=1", **options)
        assert await admin.fetchval("SELECT to_regnamespace('_analysis')") is None
        assert (
            await scanner.fetch(
                "SELECT id, md5sum FROM liquibase.databasechangelog ORDER BY id"
            )
            == before
        )
        assert (
            await scanner.fetchval(
                "SELECT jsonb_agg(to_jsonb(s)) FROM market_scanner.market_scans s"
            )
            == rows
        )
        assert (
            await sessions.fetchval(
                "SELECT id FROM _sessions.sessions WHERE id='retained-session'"
            )
            == "retained-session"
        )
    finally:
        run_liquibase(migrator, "update", **options)
        await sessions.execute(
            "DELETE FROM _sessions.sessions WHERE id='retained-session'"
        )
        await sessions.close()
        await scanner.close()
        await admin.close()


def test_result_changelog_rejects_scanner_database(migrated_database):
    with pytest.raises(RuntimeError, match="(?i)precondition"):
        run_liquibase(
            migrated_database["database_migrator"],
            "update",
            context=None,
            changelog="momentum.yaml",
        )
