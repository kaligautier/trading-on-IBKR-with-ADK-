"""Durable, user-scoped memory under the actual runtime identity."""

import asyncio
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.contracts import WorkflowExecution, WorkflowResult
from app.infrastructure.memory.postgres import PostgresMemoryRepository


@pytest.fixture
async def memory(domain_database):
    engine = create_async_engine(
        domain_database["results_runtime"].replace(
            "postgresql://", "postgresql+asyncpg://"
        ),
        pool_size=2,
        max_overflow=0,
        connect_args={"ssl": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield PostgresMemoryRepository(factory), factory
    finally:
        await engine.dispose()


def execution(user=None, ticker="AAPL"):
    return WorkflowExecution(
        user_id=user or uuid4().hex,
        session_id=uuid4().hex,
        invocation_id=uuid4().hex,
        result=WorkflowResult(
            ticker=ticker,
            analysis_date=date(2026, 1, 1),
            signal="Hold",
            final_decision="Synthetic decision",
            structured={},
            reports={},
        ),
    )


async def persist(memory, item):
    repository, factory = memory
    async with factory.begin() as session:
        return await repository.reserve(session, item)


async def test_concurrent_retry_is_one_memory_record(memory):
    item = execution()
    assert sorted(
        await asyncio.gather(persist(memory, item), persist(memory, item))
    ) == [False, True]
    snapshot = await memory[0].snapshot(item.user_id, "AAPL", date(2026, 2, 1))
    assert len(snapshot.pending) == 1
    assert snapshot.pending[0].decision == "Synthetic decision"


async def test_snapshot_is_user_scoped_and_same_date_executions_are_distinct(memory):
    first = execution()
    second = execution(first.user_id)
    await persist(memory, first)
    await persist(memory, second)
    snapshot = await memory[0].snapshot(first.user_id, "AAPL", date(2026, 2, 1))
    assert len({entry.id for entry in snapshot.pending}) == 2
    foreign = await memory[0].snapshot(uuid4().hex, "AAPL", date(2026, 2, 1))
    assert foreign.pending == ()
    assert foreign.context == ""


async def test_conflicting_retry_does_not_rewrite_decision(memory):
    item = execution()
    await persist(memory, item)
    conflict = item.model_copy(deep=True)
    conflict.result.final_decision = "Different content"
    with pytest.raises(ValueError, match="Conflicting"):
        await persist(memory, conflict)
    snapshot = await memory[0].snapshot(item.user_id, "AAPL", date(2026, 2, 1))
    assert snapshot.pending[0].decision == "Synthetic decision"


async def test_memory_reservation_rolls_back_with_its_caller(memory):
    repository, factory = memory
    item = execution()
    with pytest.raises(RuntimeError, match="injected"):
        async with factory.begin() as session:
            assert await repository.reserve(session, item)
            raise RuntimeError("injected")
    assert (
        await repository.snapshot(item.user_id, "AAPL", date(2026, 2, 1))
    ).pending == ()


async def test_pending_reads_are_bounded(memory):
    user = uuid4().hex
    for _ in range(20):
        await persist(memory, execution(user))
    assert len((await memory[0].snapshot(user, "AAPL", date(2026, 2, 1))).pending) == 16
    assert (await memory[0].snapshot(user, "AAPL", date(2025, 1, 1))).pending == ()


async def test_resolutions_use_record_identity_and_reject_foreign_users(memory):
    from app.domain.contracts import MemoryReflection

    repository, factory = memory
    item = execution()
    await persist(memory, item)
    await persist(memory, execution(item.user_id))
    entry = (await repository.snapshot(item.user_id, "AAPL", date(2026, 2, 1))).pending[
        0
    ]
    reflection = MemoryReflection(
        memory_id=entry.id,
        ticker=entry.ticker,
        trade_date=entry.analysis_date,
        decision=entry.decision,
        raw_return=0.1,
        alpha_return=0.05,
        holding_days=5,
        reflection="Synthetic lesson",
    )
    with pytest.raises(ValueError, match="memory"):
        async with factory.begin() as session:
            await repository.resolve(session, "another-user", [reflection])
    for _ in range(2):
        async with factory.begin() as session:
            await repository.resolve(session, item.user_id, [reflection])
    snapshot = await repository.snapshot(item.user_id, "AAPL", date(2026, 2, 1))
    assert len(snapshot.pending) == 1
    assert "Synthetic lesson" in snapshot.context
    reflection.reflection = "Conflicting lesson"
    with pytest.raises(ValueError, match="memory"):
        async with factory.begin() as session:
            await repository.resolve(session, item.user_id, [reflection])
    async with factory() as session:
        assert (
            await session.execute(
                text(
                    "SELECT count(*) FROM _analysis.trading_memory "
                    "WHERE user_id=:user AND reflection IS NOT NULL"
                ),
                {"user": item.user_id},
            )
        ).scalar_one() == 1


async def test_new_process_recovers_memory_without_local_files(
    memory, domain_database, tmp_path
):
    import json
    import os
    import sys
    from pathlib import Path

    item = execution()
    await persist(memory, item)
    from app.domain.contracts import MemoryReflection

    repository, factory = memory
    entry = (await repository.snapshot(item.user_id, "AAPL", date(2026, 2, 1))).pending[
        0
    ]
    async with factory.begin() as session:
        await repository.resolve(
            session,
            item.user_id,
            [
                MemoryReflection(
                    memory_id=entry.id,
                    ticker=entry.ticker,
                    trade_date=entry.analysis_date,
                    decision=entry.decision,
                    raw_return=0.1,
                    alpha_return=0.05,
                    holding_days=5,
                    reflection="Durable synthetic lesson",
                )
            ],
        )
    await persist(memory, execution(item.user_id))
    environment = os.environ.copy()
    environment.update(
        {
            "MEMORY_TEST_URL": domain_database["results_runtime"],
            "MEMORY_TEST_USER": item.user_id,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "HOME": str(tmp_path),
            "TMPDIR": str(tmp_path),
        }
    )
    program = """
import asyncio, json, os
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.infrastructure.memory.postgres import PostgresMemoryRepository
async def main():
    engine = create_async_engine(os.environ["MEMORY_TEST_URL"].replace(
        "postgresql://", "postgresql+asyncpg://"), pool_size=1, max_overflow=0,
        connect_args={"ssl": False})
    try:
        repository = PostgresMemoryRepository(async_sessionmaker(engine))
        snapshot = await repository.snapshot(os.environ["MEMORY_TEST_USER"],
            "AAPL", date(2026, 2, 1))
        print(json.dumps({"pending": [entry.decision for entry in snapshot.pending],
                          "context": snapshot.context}))
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        program,
        cwd=tmp_path,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    assert process.returncode == 0
    recovered = json.loads(stdout)
    assert recovered["pending"] == ["Synthetic decision"]
    assert "Durable synthetic lesson" in recovered["context"]
    assert not list(tmp_path.glob("**/trading_memory*"))


async def test_memory_and_results_share_admitted_connection(domain_database):
    from app.infrastructure.admission import admit_execution
    from app.infrastructure.result_repository import PostgresResultRepository
    from app.job_runner import create_result_engine

    engine = create_result_engine(domain_database["results_runtime"])
    item = execution()

    class VerifyConnectionWriter:
        async def write(self, session, _execution):
            # A single bound connection must carry admission and writes.
            assert await session.scalar(text("SELECT pg_backend_pid()")) == backend

    try:
        async with admit_execution(engine) as connection:
            factory = async_sessionmaker(connection, expire_on_commit=False)
            backend = await connection.scalar(text("SELECT pg_backend_pid()"))
            await connection.commit()
            repository = PostgresMemoryRepository(factory)
            await repository.snapshot(item.user_id, "AAPL", date(2026, 2, 1))
            assert not connection.in_transaction()
            await PostgresResultRepository(factory, VerifyConnectionWriter()).save(item)
            assert not connection.in_transaction()
            assert (
                len(
                    (
                        await repository.snapshot(
                            item.user_id, "AAPL", date(2026, 2, 1)
                        )
                    ).pending
                )
                == 1
            )
    finally:
        await engine.dispose()


async def test_resolved_context_is_bounded_and_deterministic(memory):
    from app.domain.contracts import MemoryReflection

    repository, factory = memory
    user = uuid4().hex
    for ticker, count in (("AAPL", 6), ("MSFT", 4)):
        for _ in range(count):
            await persist(memory, execution(user, ticker))
        entries = (await repository.snapshot(user, ticker, date(2026, 2, 1))).pending
        async with factory.begin() as session:
            await repository.resolve(
                session,
                user,
                [
                    MemoryReflection(
                        memory_id=entry.id,
                        ticker=entry.ticker,
                        trade_date=entry.analysis_date,
                        decision=entry.decision,
                        raw_return=0.1,
                        alpha_return=0.05,
                        holding_days=5,
                        reflection=f"lesson {entry.id}",
                    )
                    for entry in entries
                ],
            )
    context = (await repository.snapshot(user, "AAPL", date(2026, 2, 1))).context
    assert context.count("AAPL (") == 5
    assert context.count("MSFT (") == 3
    assert (
        await repository.snapshot(user, "AAPL", date(2026, 2, 1))
    ).context == context
    assert (await repository.snapshot(user, "AAPL", date(2025, 1, 1))).context == ""
