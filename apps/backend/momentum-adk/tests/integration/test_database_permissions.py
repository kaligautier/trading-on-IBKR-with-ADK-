"""Effective role permissions, including PUBLIC and inherited privileges."""

import asyncpg
import pytest


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM market_scanner.market_scans",
        "SELECT * FROM liquibase.databasechangelog",
        "SELECT * FROM public.unrelated",
        "INSERT INTO public.unrelated VALUES ('forbidden')",
        "CREATE TABLE momentum.forbidden(id INT)",
        "CREATE TABLE public.forbidden(id INT)",
        "CREATE TEMP TABLE forbidden(id INT)",
        "CREATE SCHEMA forbidden",
        "SET ROLE database_migrator",
        "CREATE ROLE forbidden",
        "ALTER TABLE momentum.sessions ADD COLUMN forbidden INT",
        "DROP TABLE momentum.events",
        "TRUNCATE momentum.sessions",
        "UPDATE momentum.adk_internal_metadata SET value='0'",
    ],
)
async def test_runtime_cannot_escape_its_schema(migrated_database, query):
    connection = await asyncpg.connect(migrated_database["momentum_writer"])
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.execute(query)
    finally:
        await connection.close()


async def test_schema_owner_and_runtime_flags(migrated_database):
    connection = await asyncpg.connect(migrated_database["admin"])
    try:
        assert (
            await connection.fetchval(
                "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=$1",
                "momentum",
            )
            == "database_migrator"
        )
        role = await connection.fetchrow(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolinherit, "
            "rolconnlimit FROM pg_roles WHERE rolname='momentum_writer'"
        )
        assert list(role.values()) == [False, False, False, False, False, 4]
        assert await connection.fetchval("SELECT value FROM public.unrelated") == (
            "preserved"
        )
    finally:
        await connection.close()


async def test_public_correction_preserves_existing_logins(migrated_database):
    from conftest import DATABASE

    connection = await asyncpg.connect(migrated_database["admin"])
    try:
        database = await connection.fetchval("SELECT current_database()")
        await connection.execute(f'GRANT TEMPORARY ON DATABASE "{database}" TO PUBLIC')
        with pytest.raises(asyncpg.RaiseError, match="effective PUBLIC"):
            await connection.execute((DATABASE / "momentum-bootstrap.sql").read_text())
        await connection.execute("ROLLBACK")
        await connection.execute(
            (DATABASE / "momentum-public-privileges.sql").read_text()
        )
        for role in ("database_migrator", "market_scanner_writer"):
            assert await connection.fetchval(
                "SELECT has_database_privilege($1, current_database(), 'TEMP')", role
            )
        assert not await connection.fetchval(
            "SELECT has_database_privilege('momentum_writer', "
            "current_database(), 'TEMP')"
        )
    finally:
        await connection.close()
