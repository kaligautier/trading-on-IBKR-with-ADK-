"""One bounded pool per process, with verified TLS and read-only sessions."""

import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    url = make_url(settings.DATABASE_URL.get_secret_value())
    tls: ssl.SSLContext | bool = False
    if url.query.get("sslmode") == "verify-full":
        ca = url.query.get("sslrootcert")
        tls = ssl.create_default_context(cafile=str(ca) if ca else None)
    url = url.difference_update_query(["sslmode", "sslrootcert"])
    url = url.set(drivername="postgresql+asyncpg")
    return create_async_engine(
        url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=0,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "ssl": tls,
            "timeout": 10,
            "server_settings": {
                "application_name": "market-scanner-api",
                "default_transaction_read_only": "on",
                "statement_timeout": "10000",
                "idle_in_transaction_session_timeout": "10000",
            },
        },
    )
