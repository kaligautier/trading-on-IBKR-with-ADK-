"""Liquibase owns result tables; the runtime can only insert and read results."""

import asyncpg
import pytest
from sqlalchemy import Float, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.models import Base


async def test_migrated_result_schema_matches_orm(domain_database):
    engine = create_async_engine(
        domain_database["admin"].replace("postgresql://", "postgresql+asyncpg://"),
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
            expected_indexes = {
                (i.name, tuple(i.columns.keys()), i.unique) for i in table.indexes
            }
            # Consultation indexes are owned by the shared database baseline.
            if table.name == "analysis_results":
                expected_indexes.update(
                    {
                        ("ix_consultation_created", ("created_at", "id"), False),
                        (
                            "ix_consultation_ticker_created",
                            ("ticker", "created_at", "id"),
                            False,
                        ),
                    }
                )
            else:
                expected_indexes.add(
                    (f"ix_consultation_{table.name}_result", ("result_id", "id"), False)
                )
            assert {
                (i["name"], tuple(i["column_names"]), i["unique"])
                for i in inspector.get_indexes(table.name, "_analysis")
            } == expected_indexes
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


async def test_result_tables_have_only_explicit_runtime_grants(domain_database):
    admin = await asyncpg.connect(domain_database["admin"])
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
async def test_runtime_cannot_modify_completed_results(domain_database, query):
    writer = await asyncpg.connect(domain_database["results_runtime"])
    transaction = writer.transaction()
    await transaction.start()
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await writer.execute(query)
    finally:
        await transaction.rollback()
        await writer.close()
