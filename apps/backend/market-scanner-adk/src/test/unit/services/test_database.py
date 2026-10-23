"""Pool lifecycle, bounded configuration and TLS regression checks."""

import ssl
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, settings
from app.services import database


def should_use_verified_tls_without_forwarding_libpq_keywords():
    from app.services.postgres_tls import connection_options

    address, tls = connection_options(
        "postgresql://writer:private@db.example/market_scanner?sslmode=verify-full"
    )
    assert address.query == {}
    assert isinstance(tls, ssl.SSLContext)
    assert tls.check_hostname
    assert tls.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?sslmode=require",
        "?sslmode=disable",
        "?ssl=prefer",
        "?sslmode=verify-ca",
        "?sslmode=verify-full&ssl=disable",
        "?sslmode=verify-full&sslmode=disable",
        "?sslmode=verify-full&unexpected=x",
    ],
)
def should_reject_remote_insecure_or_ambiguous_options_without_leaking(query):
    from app.services.postgres_tls import connection_options

    with pytest.raises(ValueError) as error:
        connection_options(
            "postgresql://writer:private@db.example/market_scanner" + query
        )
    assert "private" not in str(error.value)
    assert "db.example" not in str(error.value)


def should_consume_ca_option_and_reject_unreadable_ca(tmp_path):
    from app.services.postgres_tls import connection_options

    with pytest.raises(ValueError, match="PostgreSQL"):
        connection_options(
            "postgresql://writer:private@db.example/market_scanner?sslmode=verify-full"
            f"&sslrootcert={tmp_path / 'missing.pem'}"
        )


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def should_allow_explicit_local_development_without_tls(host):
    from app.services.postgres_tls import connection_options

    address, tls = connection_options(
        f"postgresql://writer@{host}/test?sslmode=disable"
    )
    assert tls is False
    assert address.query == {}


async def should_reuse_the_pool_until_shutdown_and_then_recreate_it(monkeypatch):
    engine = Mock(dispose=AsyncMock())
    factory = Mock(return_value=engine)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "create_async_engine", factory)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgres://writer@localhost/scanner")
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
