"""Private durable memory with narrowly scoped runtime privileges."""

import asyncpg
import pytest


async def test_memory_is_private_and_execution_identity_is_unique(domain_database):
    admin = await asyncpg.connect(domain_database["admin"])
    try:
        assert await admin.fetchval("SELECT to_regclass('_analysis.trading_memory')")
        assert (
            await admin.fetchval(
                "SELECT tableowner FROM pg_tables WHERE schemaname='_analysis' "
                "AND tablename='trading_memory'"
            )
            == "database_migrator"
        )
        constraints = await admin.fetch(
            "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
            "WHERE conrelid='_analysis.trading_memory'::regclass"
        )
        assert any(
            row["definition"] == "UNIQUE (user_id, session_id, invocation_id)"
            for row in constraints
        )
        assert not await admin.fetchval(
            "SELECT has_table_privilege('momentum_results_reader', "
            "'_analysis.trading_memory', 'SELECT')"
        )
    finally:
        await admin.close()


@pytest.mark.parametrize(
    "role", ["momentum_results_reader", "momentum_sessions_writer"]
)
async def test_other_runtime_identities_cannot_read_memory(domain_database, role):
    url = domain_database["results_runtime"].replace("momentum_results_writer", role)
    connection = await asyncpg.connect(url)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.fetch("SELECT * FROM _analysis.trading_memory")
    finally:
        await connection.close()


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE _analysis.trading_memory SET user_id='other'",
        "UPDATE _analysis.trading_memory SET decision='rewritten'",
        "DELETE FROM _analysis.trading_memory",
        "ALTER TABLE _analysis.trading_memory ADD COLUMN forbidden int",
    ],
)
async def test_memory_writer_cannot_rewrite_identity_or_decisions(
    domain_database, query
):
    writer = await asyncpg.connect(domain_database["results_runtime"])
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await writer.execute(query)
    finally:
        await writer.close()
