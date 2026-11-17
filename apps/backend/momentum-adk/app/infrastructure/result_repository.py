"""Atomic persistence of financial sections and their ADK execution correlation."""

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.contracts import WorkflowExecution
from app.infrastructure.memory.postgres import PostgresMemoryRepository


class ResultWriter(Protocol):
    async def write(self, session: AsyncSession, execution: WorkflowExecution) -> None:
        """Add result rows inside the supplied transaction, without committing."""


class PostgresResultRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        result_writer: ResultWriter,
    ) -> None:
        self._session_factory = session_factory
        self._result_writer = result_writer
        self._memory = PostgresMemoryRepository(session_factory)

    async def save(self, execution: WorkflowExecution) -> None:
        """Commit every section together; exceptions roll back and close the session."""
        async with self._session_factory() as session, session.begin():
            if not await self._memory.reserve(session, execution):
                return
            await self._result_writer.write(session, execution)
            await self._memory.resolve(
                session, execution.user_id, execution.result.memory_reflections
            )
