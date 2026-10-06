"""One bounded PostgreSQL pool per application process, opened lazily."""

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import settings

_engine: AsyncEngine | None = None


def async_database_url(database_url: str) -> str:
    """Preserve TLS settings while translating PostgreSQL URLs for asyncpg."""
    address = make_url(database_url)
    if address.drivername in {"postgres", "postgresql"}:
        address = address.set(drivername="postgresql+asyncpg")
    ssl_mode = address.query.get("sslmode")
    if ssl_mode is not None:
        address = address.difference_update_query(["sslmode"])
        address = address.update_query_dict({"ssl": ssl_mode})
    return address.render_as_string(hide_password=False)


def get_engine() -> AsyncEngine:
    """Reuse the same pool across concurrent scans; sessions stay independent."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            async_database_url(settings.DATABASE_URL),
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=0,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
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
