"""Atomic suggestion intake using the API's existing bounded connection pool."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.adapters.postgresql.repository import storage_error
from app.domain.suggestions import (
    CurrentAnalysisExistsError,
    Suggestion,
    SuggestionInput,
    SuggestionRateLimitError,
)

# Only public fields leave the repository; caller hashes and reviewer IDs stay private.
COLUMNS = "id,symbol,reason,status,source,created_at,reviewed_at,review_reason"


def suggestion(row: RowMapping) -> Suggestion:
    return Suggestion(**{name: row[name] for name in COLUMNS.split(",")})


class SuggestionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def get(self, suggestion_id: UUID) -> Suggestion | None:
        try:
            async with self.engine.connect() as connection, connection.begin():
                row = (
                    (
                        await connection.execute(
                            text(
                                "SELECT id,symbol,reason,status,source,created_at,"
                                "reviewed_at,review_reason "
                                "FROM _suggestions.ticker_suggestions WHERE id=:id"
                            ),
                            {"id": suggestion_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                return suggestion(row) if row else None
        except (SQLAlchemyError, TimeoutError, OSError) as error:
            raise storage_error(error) from error

    async def submit(self, request: SuggestionInput) -> Suggestion:
        try:
            async with self.engine.connect() as connection, connection.begin():
                # Scoped to this transaction only. AnalysisRepository still forces
                # READ ONLY and the role has no analysis write privileges.
                await connection.execute(text("SET TRANSACTION READ WRITE"))
                await connection.execute(
                    text(
                        "SELECT pg_advisory_xact_lock(hashtextextended(:caller,2575))"
                    ),
                    {"caller": request.caller},
                )
                existing = await self._find(connection, request.symbol)
                if existing:
                    return existing
                await self._validate_policy(connection, request)
                row = (
                    (
                        await connection.execute(
                            text(
                                "INSERT INTO _suggestions.ticker_suggestions"
                                "(symbol,reason,suggested_by) "
                                "VALUES (:symbol,:reason,:caller) "
                                "ON CONFLICT(symbol) DO NOTHING RETURNING "
                                "id,symbol,reason,status,source,created_at,"
                                "reviewed_at,review_reason"
                            ),
                            {
                                "symbol": request.symbol,
                                "reason": request.reason,
                                "caller": request.caller,
                            },
                        )
                    )
                    .mappings()
                    .first()
                )
                # A simultaneous proposal from another caller resolves to the same ID.
                result = (
                    suggestion(row)
                    if row
                    else await self._find(connection, request.symbol)
                )
                if result is None:
                    raise RuntimeError("Suggestion disappeared during intake")
                return result  # Context manager commits before the caller receives it.
        except (SQLAlchemyError, TimeoutError, OSError) as error:
            raise storage_error(error) from error

    @staticmethod
    async def _find(connection: AsyncConnection, symbol: str) -> Suggestion | None:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT id,symbol,reason,status,source,created_at,"
                        "reviewed_at,review_reason "
                        "FROM _suggestions.ticker_suggestions WHERE symbol=:symbol"
                    ),
                    {"symbol": symbol},
                )
            )
            .mappings()
            .first()
        )
        return suggestion(row) if row else None

    @staticmethod
    async def _validate_policy(
        connection: AsyncConnection, request: SuggestionInput
    ) -> None:
        freshness = (
            await connection.execute(
                text(
                    "SELECT next_analysis_date FROM _analysis.analysis_results "
                    "WHERE ticker=:symbol ORDER BY created_at DESC,id DESC LIMIT 1"
                ),
                {"symbol": request.symbol},
            )
        ).first()
        if freshness and (
            freshness[0] is None or freshness[0] >= datetime.now(UTC).date()
        ):
            raise CurrentAnalysisExistsError()
        quota = (
            await connection.execute(
                text("""
            SELECT count(*) FILTER (
                WHERE created_at >= date_trunc('day',now() AT TIME ZONE 'UTC')
                    AT TIME ZONE 'UTC') AS today,
              coalesce(max(created_at) > now() - interval '15 minutes',
                       false) AS cooldown
            FROM _suggestions.ticker_suggestions
            WHERE suggested_by=:caller AND source='mcp'
        """),
                {"caller": request.caller},
            )
        ).one()
        if quota.cooldown or quota.today >= 5:
            raise SuggestionRateLimitError()
