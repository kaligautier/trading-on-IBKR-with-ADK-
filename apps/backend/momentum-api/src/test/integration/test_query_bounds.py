"""Batch count does not grow with page size; measured index access paths."""

import json
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import event

from app.domain.analyses.search import AnalysisSearchParams

from .conftest import seed

BOOTSTRAP = (
    Path(__file__).resolve().parents[6] / "database/momentum-reader-bootstrap.sql"
).read_text()


async def test_summary_loading_is_batched(admin, service):
    await seed(admin, 125)
    reader, engine = service
    statements = []

    def record(_, __, statement, *args):
        if statement.startswith("SELECT"):
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        counts = []
        for size in (1, 100):
            statements.clear()
            await reader.list(
                AnalysisSearchParams.from_parameters("history", None, None, size, "")
            )
            counts.append(len(statements))
        assert counts == [5, 5]  # One bounded header query plus four financial batches.
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


async def test_ordering_index_and_latest_access_plan(admin):
    await admin.execute("""INSERT INTO _analysis.analysis_results
        (id,ticker,analysis_date,llm_provider,deep_think_llm,quick_think_llm,
         created_at,session_id,invocation_id,user_id)
        SELECT md5(n::text)::uuid,'T'||(n%1000)::text,'2026-10-22','synthetic',
               'test','test','2026-10-22T12:00:00Z','fixture','fixture','fixture'
        FROM generate_series(1,10000) n""")
    await admin.execute("ANALYZE _analysis.analysis_results")
    plan = json.loads(
        await admin.fetchval("""EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
        SELECT id,ticker,created_at FROM _analysis.analysis_results
        ORDER BY created_at DESC,id DESC LIMIT 20""")
    )[0]
    assert "ix_consultation_created" in json.dumps(plan)
    latest = json.loads(
        await admin.fetchval("""EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
        SELECT DISTINCT ON(ticker) id,ticker,created_at FROM _analysis.analysis_results
        ORDER BY ticker,created_at DESC,id DESC""")
    )[0]
    assert latest["Plan"]["Actual Rows"] == 1000
    print(
        "Synthetic 10,000 results: history index",
        plan["Execution Time"],
        "ms; latest full-catalogue plan",
        latest["Execution Time"],
        "ms",
    )


async def test_reader_bootstrap_refuses_effective_public_or_direct_write_privileges(
    admin,
):
    # Bootstrap rolls back on failure; the test restores only its own grant.
    for grant, revoke in (
        (
            "GRANT TEMP ON DATABASE momentum TO PUBLIC",
            "REVOKE TEMP ON DATABASE momentum FROM PUBLIC",
        ),
        (
            "GRANT INSERT ON _analysis.analysis_results TO momentum_results_reader",
            "REVOKE INSERT ON _analysis.analysis_results FROM momentum_results_reader",
        ),
        (
            "GRANT UPDATE(ticker) ON _analysis.analysis_results "
            "TO momentum_results_reader",
            "REVOKE UPDATE(ticker) ON _analysis.analysis_results "
            "FROM momentum_results_reader",
        ),
        (
            "GRANT SELECT ON _analysis.analysis_results "
            "TO momentum_results_reader WITH GRANT OPTION",
            "REVOKE GRANT OPTION FOR SELECT ON _analysis.analysis_results "
            "FROM momentum_results_reader",
        ),
    ):
        await admin.execute(grant)
        try:
            with pytest.raises(asyncpg.RaiseError):
                await admin.execute(BOOTSTRAP)
            await admin.execute("ROLLBACK")
        finally:
            await admin.execute(revoke)
    assert not await admin.fetchval(
        "SELECT has_table_privilege('momentum_results_reader', "
        "'_analysis.analysis_results', 'INSERT')"
    )


@pytest.mark.parametrize("grantee", ["momentum_results_reader", "PUBLIC"])
async def test_bootstrap_refuses_column_reads_outside_analysis(admin, grantee):
    await admin.execute("CREATE TABLE public.bootstrap_probe(value text)")
    await admin.execute("GRANT SELECT(value) ON public.bootstrap_probe TO " + grantee)
    try:
        with pytest.raises(asyncpg.RaiseError):
            await admin.execute(BOOTSTRAP)
    finally:
        await admin.execute("ROLLBACK")
        await admin.execute("DROP TABLE public.bootstrap_probe")


@pytest.mark.parametrize("grantee", ["PUBLIC", "momentum_results_reader"])
@pytest.mark.parametrize("privilege", ["SELECT", "SELECT(id)"])
@pytest.mark.parametrize("schema", ["_analysis", "reader_private"])
async def test_bootstrap_rejects_reads_of_unapproved_analysis_relations(
    admin, grantee, privilege, schema
):
    if schema == "reader_private":
        await admin.execute("CREATE SCHEMA reader_private")
        await admin.execute("GRANT USAGE ON SCHEMA reader_private TO " + grantee)
    relation = schema + ".reader_privacy_probe"
    await admin.execute("CREATE TABLE " + relation + "(id integer)")
    try:
        await admin.execute("GRANT " + privilege + " ON " + relation + " TO " + grantee)
        with pytest.raises(asyncpg.RaiseError):
            await admin.execute(BOOTSTRAP)
        await admin.execute("ROLLBACK")
    finally:
        await admin.execute("ROLLBACK")
        await admin.execute("DROP TABLE " + relation)
        if schema == "reader_private":
            await admin.execute("DROP SCHEMA reader_private")


async def test_bootstrap_rejects_effective_cross_database_connect(admin):
    await admin.execute("CREATE DATABASE reader_isolation_probe")
    await admin.execute("GRANT CONNECT ON DATABASE reader_isolation_probe TO PUBLIC")
    try:
        with pytest.raises(asyncpg.RaiseError):
            await admin.execute(BOOTSTRAP)
        await admin.execute("ROLLBACK")
        await admin.execute(
            "REVOKE CONNECT ON DATABASE reader_isolation_probe FROM PUBLIC"
        )
        await admin.execute(BOOTSTRAP)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await asyncpg.connect(
                "postgresql://momentum_results_reader:local-only@"
                "127.0.0.1:55451/reader_isolation_probe"
            )
    finally:
        await admin.execute("DROP DATABASE reader_isolation_probe")
