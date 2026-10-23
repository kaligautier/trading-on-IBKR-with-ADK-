"""Bounded private memory, sharing the result transaction and connection pool."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.contracts import MemoryReflection, WorkflowExecution


@dataclass(frozen=True)
class MemoryEntry:
    id: UUID
    ticker: str
    analysis_date: date
    decision: str


@dataclass(frozen=True)
class MemorySnapshot:
    context: str
    pending: tuple[MemoryEntry, ...]


class PostgresMemoryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def snapshot(
        self, user_id: str, ticker: str, before_date: date
    ) -> MemorySnapshot:
        parameters = {"user": user_id, "ticker": ticker, "before": before_date}
        async with self._factory() as session:
            pending = (
                (
                    await session.execute(
                        text("""
                SELECT id, ticker, analysis_date, decision FROM _analysis.trading_memory
                WHERE user_id=:user AND ticker=:ticker AND reflection IS NULL
                    AND analysis_date < :before
                ORDER BY analysis_date, id LIMIT 16
            """),
                        parameters,
                    )
                )
                .mappings()
                .all()
            )
            context = []
            for comparison, limit in (("=", 5), ("<>", 3)):
                rows = await session.execute(
                    text(f"""
                    SELECT ticker, analysis_date, decision, reflection
                    FROM _analysis.trading_memory
                    WHERE user_id=:user AND ticker {comparison} :ticker
                        AND reflection IS NOT NULL AND analysis_date < :before
                    ORDER BY created_at DESC, id DESC LIMIT {limit}
                """),
                    parameters,
                )
                context.extend(
                    f"{row.ticker} ({row.analysis_date}): {row.decision}\n"
                    f"Reflection: {row.reflection}"
                    for row in rows
                )
        return MemorySnapshot(
            "\n\n".join(context), tuple(MemoryEntry(**row) for row in pending)
        )

    async def reserve(
        self, session: AsyncSession, execution: WorkflowExecution
    ) -> bool:
        payload = execution.result.model_dump(
            mode="json", exclude={"run_stats": {"duration_seconds"}}
        )
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        parameters = {
            "id": uuid4(),
            "user": execution.user_id,
            "session": execution.session_id,
            "invocation": execution.invocation_id,
            "ticker": execution.result.ticker,
            "date": execution.result.analysis_date,
            "decision": execution.result.final_decision,
            "digest": digest,
        }
        inserted = await session.execute(
            text("""
            INSERT INTO _analysis.trading_memory
                (id, user_id, session_id, invocation_id, ticker, analysis_date,
                 decision, completion_digest)
            VALUES (:id, :user, :session, :invocation, :ticker, :date,
                    :decision, :digest)
            ON CONFLICT (user_id, session_id, invocation_id) DO NOTHING RETURNING id
        """),
            parameters,
        )
        if inserted.scalar_one_or_none() is not None:
            return True
        previous = await session.execute(
            text("""
            SELECT completion_digest FROM _analysis.trading_memory
            WHERE user_id=:user AND session_id=:session AND invocation_id=:invocation
        """),
            parameters,
        )
        if previous.scalar_one() != digest:
            raise ValueError("Conflicting completion for existing memory execution")
        return False

    async def resolve(
        self, session: AsyncSession, user_id: str, reflections: list[MemoryReflection]
    ) -> None:
        for reflection in reflections:
            await self._resolve_one(session, user_id, reflection)

    @staticmethod
    async def _resolve_one(
        session: AsyncSession, user_id: str, reflection: MemoryReflection
    ) -> None:
        parameters = reflection.model_dump()
        parameters["user"] = user_id
        current = (
            (
                await session.execute(
                    text("""
            SELECT raw_return, alpha_return, holding_days, reflection
            FROM _analysis.trading_memory
            WHERE id=:memory_id AND user_id=:user AND ticker=:ticker
                AND analysis_date=:trade_date AND decision=:decision FOR UPDATE
        """),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise ValueError("Unknown or foreign memory record")
        if current["reflection"] is not None:
            if any(current[key] != parameters[key] for key in current):
                raise ValueError("Conflicting memory reflection")
            return
        await session.execute(
            text("""
            UPDATE _analysis.trading_memory SET raw_return=:raw_return,
                alpha_return=:alpha_return, holding_days=:holding_days,
                reflection=:reflection, resolved_at=CURRENT_TIMESTAMP
            WHERE id=:memory_id AND user_id=:user
        """),
            parameters,
        )
