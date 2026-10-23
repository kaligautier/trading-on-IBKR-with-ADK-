"""One bounded PostgreSQL pool per application process, opened lazily."""

import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import settings
from app.services.postgres_tls import connection_options

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Reuse the same pool across concurrent scans; sessions stay independent."""
    global _engine
    if _engine is None:
        address, tls = connection_options(
            settings.DATABASE_URL, os.getenv("DATABASE_CA_FILE")
        )
        _engine = create_async_engine(
            address,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=0,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "ssl": tls,
                "timeout": 10,
                "server_settings": {
                    "application_name": "market-scanner-adk",
                    "statement_timeout": "30000",
                    "idle_in_transaction_session_timeout": "30000",
                },
            },
        )
    return _engine


async def close_database() -> None:
    """Release the pool on application shutdown, including exceptional exits."""
    global _engine
    if _engine is not None:
        engine, _engine = _engine, None
        await engine.dispose()
