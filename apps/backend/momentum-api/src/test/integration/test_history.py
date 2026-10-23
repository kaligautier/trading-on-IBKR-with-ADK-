"""Real ordering, read transactions and failure classification."""

from uuid import UUID

import pytest
from sqlalchemy import text

from app.domain.analyses.errors import StoreConfigurationError, StoreUnavailableError
from app.domain.analyses.search import AnalysisSearchParams

from .conftest import seed


def query(page_token="", page_size=20, ticker=None):
    return AnalysisSearchParams.from_parameters(
        "history", ticker, None, page_size, page_token
    )


async def test_empty_history_and_bounded_keyset_traversal(admin, service):
    reader, engine = service
    assert (await reader.list(query())).items == []
    await seed(admin, 125)
    ids, token = [], ""
    while True:
        page = await reader.list(query(token, 17))
        assert len(page.items) <= 17
        ids.extend(item.id for item in page.items)
        token = page.next_page_token
        if not token:
            break
    assert ids == [UUID(int=index) for index in range(125, 0, -1)]
    assert engine.pool.checkedout() == 0
    assert (await reader.list(query(ticker="missing"))).items == []
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SHOW transaction_read_only"))
        ).scalar() == "on"


async def test_unknown_schema_is_configuration_failure_and_releases_connection(
    admin, service
):
    reader, engine = service
    await admin.execute("ALTER SCHEMA _analysis RENAME TO temporarily_hidden")
    try:
        with pytest.raises(StoreConfigurationError):
            await reader.list(query())
        assert engine.pool.checkedout() == 0
    finally:
        await admin.execute("ALTER SCHEMA temporarily_hidden RENAME TO _analysis")


async def test_timeout_is_transient_and_does_not_leak_driver_details(admin, service):
    reader, engine = service
    transaction = admin.transaction()
    await transaction.start()
    await admin.execute("LOCK _analysis.analysis_results IN ACCESS EXCLUSIVE MODE")
    try:
        with pytest.raises(StoreUnavailableError) as caught:
            await reader.list(query())
        assert "postgresql" not in str(caught.value)
        assert engine.pool.checkedout() == 0
    finally:
        await transaction.rollback()


async def test_missing_optional_physical_column_is_configuration_error(admin, service):
    reader, _ = service
    await seed(admin)
    await admin.execute(
        "ALTER TABLE _analysis.technical_indicators RENAME COLUMN rsi TO missing_rsi"
    )
    try:
        for operation in (reader.ready, lambda: reader.list(query())):
            with pytest.raises(StoreConfigurationError):
                await operation()
    finally:
        await admin.execute(
            "ALTER TABLE _analysis.technical_indicators "
            "RENAME COLUMN missing_rsi TO rsi"
        )
