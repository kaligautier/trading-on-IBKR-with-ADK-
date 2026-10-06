"""Pool lifecycle, bounded configuration and TLS regression checks."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, settings
from app.services import database


async def should_reuse_the_pool_until_shutdown_and_then_recreate_it(monkeypatch):
    engine = Mock(dispose=AsyncMock())
    factory = Mock(return_value=engine)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "create_async_engine", factory)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgres://writer@db/scanner")
    monkeypatch.setattr(settings, "DATABASE_POOL_SIZE", 1)

    assert database.get_engine() is database.get_engine() is engine
    factory.assert_called_once()
    assert factory.call_args.kwargs["pool_size"] == 1
    assert factory.call_args.kwargs["max_overflow"] == 0
    assert factory.call_args.kwargs["pool_pre_ping"] is True
    await database.close_database()
    await database.close_database()
    engine.dispose.assert_awaited_once()
    database.get_engine()
    assert factory.call_count == 2
    await database.close_database()


@pytest.mark.parametrize(
    "overrides",
    [
        {"DATABASE_SCHEMA": 'public"; DROP SCHEMA public; --'},
        {"DATABASE_SCHEMA": "public,market_scanner"},
        {"DATABASE_POOL_SIZE": 0},
        {"DATABASE_POOL_SIZE": -1},
        {"DATABASE_POOL_TIMEOUT": 0},
    ],
)
def should_reject_unsafe_schema_names_and_unbounded_pools(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, GOOGLE_CLOUD_PROJECT="test", **overrides)


def should_prefer_the_scanner_credential_in_a_shared_environment(monkeypatch):
    monkeypatch.setenv("MARKET_SCANNER_DATABASE_URL", "postgres://writer@db/scanner")
    monkeypatch.setenv("TA_DATABASE_URL", "postgres://other@db/other")
    configuration = Settings(_env_file=None, GOOGLE_CLOUD_PROJECT="test")
    assert configuration.DATABASE_URL == "postgres://writer@db/scanner"
