"""One Momentum database, two isolated schemas, existing Scanner untouched."""

import asyncpg
import pytest


@pytest.mark.parametrize(
    "key,own,other,count",
    [
        ("sessions_runtime", "_sessions", "_analysis", 5),
        ("results_runtime", "_analysis", "_sessions", 13),
    ],
)
async def test_schema_isolation_in_one_database(
    domain_database, key, own, other, count
):
    connection = await asyncpg.connect(domain_database[key])
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
