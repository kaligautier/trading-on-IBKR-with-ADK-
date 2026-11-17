"""Admit one Momentum execution across processes on its result connection."""

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import text


class MomentumBusyError(RuntimeError):
    """Another worker owns the Momentum execution slot."""


@asynccontextmanager
async def admit_execution(engine):
    async with engine.connect() as connection:
        try:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(73192002)")
            )
            await connection.commit()
            if not acquired:
                raise MomentumBusyError("Momentum execution capacity is busy")
            yield connection
        finally:
            # Physical closure releases even a lock acquired just before cancellation.
            await asyncio.shield(connection.invalidate())
