"""Recovered intake policy and permissions exercised against real PostgreSQL."""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from sqlalchemy import text

from app.adapters.postgresql.connection import create_engine
from app.adapters.postgresql.suggestions import SuggestionRepository
from app.config.settings import Settings
from app.domain.suggestions import (
    CurrentAnalysisExistsError,
    SuggestionInput,
    SuggestionRateLimitError,
)

from .conftest import BASE, seed


@pytest.fixture
async def suggestions(service, admin):
    await admin.execute("TRUNCATE _suggestions.ticker_suggestions")
    _, engine = service
    try:
        yield SuggestionRepository(engine), engine
    finally:
        await admin.execute("TRUNCATE _suggestions.ticker_suggestions")


async def test_persist_pending_and_read_after_reconnecting(suggestions, admin):
    repository, engine = suggestions
    value = await repository.submit(SuggestionInput(" msft ", " rationale ", "a" * 64))
    assert value.symbol == "MSFT" and value.reason == "rationale"
    assert value.status == "pending" and value.source == "mcp"
    assert "suggested_by" not in asdict(value)
    await engine.dispose()
    assert await repository.get(value.id) == value
    assert (
        await admin.fetchval("SELECT count(*) FROM _suggestions.ticker_suggestions")
        == 1
    )
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SHOW transaction_read_only"))
        ).scalar() == "on"


async def test_duplicate_returns_same_id_before_cooldown(suggestions):
    repository, _ = suggestions
    first = await repository.submit(SuggestionInput("MSFT", "first", "a" * 64))
    second = await repository.submit(SuggestionInput("MSFT", "second", "a" * 64))
    assert first == second


async def test_atomic_cooldown_for_concurrent_intake(suggestions, admin):
    repository, _ = suggestions
    # Only this disposable test simulates two replicas; production retains one pool.
    await admin.execute("ALTER ROLE momentum_results_reader CONNECTION LIMIT 2")
    other_engine = create_engine(
        Settings(
            _env_file=None,
            DATABASE_URL=BASE.format("momentum_results_reader"),
            API_TOKEN="disposable-test-token",
            AUTH_MODE="token",
        )
    )
    try:
        other = SuggestionRepository(other_engine)
        results = await asyncio.gather(
            repository.submit(SuggestionInput("MSFT", "", "a" * 64)),
            other.submit(SuggestionInput("NVDA", "", "a" * 64)),
            return_exceptions=True,
        )
    finally:
        await other_engine.dispose()
        await admin.execute("ALTER ROLE momentum_results_reader CONNECTION LIMIT 1")
    assert sum(isinstance(value, SuggestionRateLimitError) for value in results) == 1
    assert sum(not isinstance(value, Exception) for value in results) == 1


async def test_daily_limit_independent_of_cooldown(suggestions, admin):
    repository, _ = suggestions
    # Seed five records today; just after midnight both limits may apply.
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    await admin.executemany(
        """
        INSERT INTO _suggestions.ticker_suggestions
            (symbol,reason,suggested_by,created_at)
        VALUES ($1,'',$3,$2)
    """,
        [
            (f"Q{i}", max(day_start, now - timedelta(minutes=16)), "a" * 64)
            for i in range(5)
        ],
    )
    with pytest.raises(SuggestionRateLimitError):
        await repository.submit(SuggestionInput("NVDA", "", "a" * 64))


@pytest.mark.parametrize(
    "expiry,allowed", [(None, False), (-1, True), (0, False), (1, False)]
)
async def test_original_analysis_expiry_policy(suggestions, admin, expiry, allowed):
    repository, _ = suggestions
    await seed(admin)
    await admin.execute(
        "UPDATE _analysis.analysis_results SET next_analysis_date=$1",
        None if expiry is None else datetime.now(UTC).date() + timedelta(days=expiry),
    )
    request = SuggestionInput("T000", "", "a" * 64)
    if allowed:
        assert (await repository.submit(request)).status == "pending"
    else:
        with pytest.raises(CurrentAnalysisExistsError):
            await repository.submit(request)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE _suggestions.ticker_suggestions SET status='approved' WHERE false",
        "DELETE FROM _suggestions.ticker_suggestions WHERE false",
        "TRUNCATE _suggestions.ticker_suggestions",
        "INSERT INTO _suggestions.ticker_suggestions"
        "(symbol,reason,suggested_by,status) "
        "VALUES ('X','',repeat('a',64),'approved')",
        "INSERT INTO _analysis.analysis_results "
        "SELECT * FROM _analysis.analysis_results WHERE false",
        "CREATE TABLE _suggestions.forbidden(id int)",
    ],
)
async def test_intake_grant_cannot_review_or_write_analyses(suggestions, statement):
    connection = await asyncpg.connect(BASE.format("momentum_results_reader"))
    try:
        await connection.execute("SET default_transaction_read_only=off")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.execute(statement)
    finally:
        await connection.close()


async def test_bootstrap_rejects_extra_suggestion_column_grants(suggestions, admin):
    from .test_query_bounds import BOOTSTRAP

    for column in ("status", "created_at", "source", "reviewed_by"):
        await admin.execute(
            f"GRANT INSERT({column}) ON _suggestions.ticker_suggestions "
            "TO momentum_results_reader"
        )
        try:
            with pytest.raises(asyncpg.RaiseError):
                await admin.execute(BOOTSTRAP)
            await admin.execute("ROLLBACK")
        finally:
            await admin.execute(
                f"REVOKE INSERT({column}) ON _suggestions.ticker_suggestions "
                "FROM momentum_results_reader"
            )
