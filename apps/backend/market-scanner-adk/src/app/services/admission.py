"""Cross-process admission reusing the result connection without a transaction."""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.services.database import get_engine

_current: ContextVar[AsyncConnection | None] = ContextVar(
    "scan_connection", default=None
)


class ScannerBusyError(RuntimeError):
    """A different HTTP request or job owns the database execution slot."""


def result_bind():
    connection = _current.get()
    if connection is None:
        return get_engine()
    if connection.invalidated or connection.closed:
        raise RuntimeError("Scanner admission connection was lost")
    return connection


@asynccontextmanager
async def admit_scan():
    # Null/idle session pools must not occupy the probe slot before this lock.
    async with get_engine().connect() as connection:
        token = None
        try:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(73192001)")
            )
            await connection.commit()
            if not acquired:
                raise ScannerBusyError("Scanner execution capacity is busy")
            token = _current.set(connection)
            yield connection
        finally:
            if token is not None:
                _current.reset(token)
            # Close the session even when cancellation follows lock acquisition.
            # Never return a session-level lock to the idle pool.
            await asyncio.shield(connection.invalidate())
