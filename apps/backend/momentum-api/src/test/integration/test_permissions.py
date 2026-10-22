"""Effective reader privileges, independent of a changeable read-only setting."""

import asyncpg
import pytest

from .conftest import BASE


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO _analysis.analysis_results "
        "SELECT * FROM _analysis.analysis_results WHERE false",
        "UPDATE _analysis.analysis_results SET ticker=ticker WHERE false",
        "DELETE FROM _analysis.analysis_results WHERE false",
        "TRUNCATE _analysis.analysis_results",
        "CREATE TABLE _analysis.forbidden(id int)",
        "CREATE TABLE public.forbidden(id int)",
        "CREATE TEMP TABLE forbidden(id int)",
        "CREATE SCHEMA forbidden",
        "SELECT * FROM _sessions.sessions",
        "SELECT * FROM liquibase.databasechangelog",
    ],
)
async def test_reader_denied_without_relying_on_read_only(admin, statement):
    connection = await asyncpg.connect(BASE.format("momentum_results_reader"))
    try:
        assert await connection.fetchval("SHOW default_transaction_read_only") == "on"
        await connection.execute("SET default_transaction_read_only = off")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.execute(statement)
    finally:
        await connection.close()


async def test_no_memberships_or_public_read_and_writer_grants_preserved(admin):
    assert (
        await admin.fetchval("""SELECT count(*) FROM pg_auth_members m
        JOIN pg_roles r ON r.oid=m.member WHERE r.rolname='momentum_results_reader' """)
        == 0
    )
    assert await admin.fetchval(
        "SELECT has_table_privilege('momentum_results_writer', "
        "'_analysis.analysis_results', 'INSERT')"
    )
    await admin.execute("CREATE TABLE public.permission_probe(value text)")
    connection = await asyncpg.connect(BASE.format("momentum_results_reader"))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.fetch("SELECT * FROM public.permission_probe")
    finally:
        await connection.close()
        await admin.execute("DROP TABLE public.permission_probe")
