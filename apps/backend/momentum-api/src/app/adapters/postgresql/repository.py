"""Bounded, schema-qualified queries; never write or migrate at runtime."""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.adapters.postgresql.mapper import SECTION_MODELS, Row, StoredAnalysis
from app.domain.analyses.search import AnalysisSearchParams
from app.presentation.http.problems import APIError

HEADER_COLUMNS = (
    "id, ticker, analysis_date, created_at, llm_provider, deep_think_llm, "
    "quick_think_llm, next_analysis_date, next_analysis_desc"
)
SUMMARY_TABLES = (
    "technical_indicators",
    "fundamentals",
    "portfolio_decisions",
    "trader_proposals",
)


SECTION_COLUMNS = {
    table: ", ".join(
        (
            "id",
            "result_id",
            *(
                str(field.validation_alias or name)
                for name, field in model.model_fields.items()
                if name != "items"
            ),
        )
    )
    for table, model in SECTION_MODELS.items()
}


def storage_error(error: Exception) -> APIError:
    cause: BaseException | None = error
    while cause is not None:
        state = getattr(cause, "sqlstate", None)
        if state is not None and (state[:2] in {"28", "42", "3D", "3F"}):
            return APIError(500, "configuration-error")
        cause = cause.__cause__
    if isinstance(error, ProgrammingError):
        return APIError(500, "configuration-error")
    return APIError(503, "store-unavailable")


class AnalysisRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncConnection]:
        try:
            async with self.engine.connect() as connection, connection.begin():
                await connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                yield connection
        except (SQLAlchemyError, TimeoutError, OSError) as error:
            raise storage_error(error) from None

    async def load(
        self,
        connection: AsyncConnection,
        headers: Sequence[Row],
        tables: tuple[str, ...],
    ) -> list[StoredAnalysis]:
        ids = [cast(UUID, row["id"]) for row in headers]
        sections: dict[UUID, dict[str, list[Row]]] = {key: {} for key in ids}
        if ids:
            for table in tables:
                if table not in SECTION_MODELS:
                    raise ValueError("Unsupported section")
                statement = text(
                    f"SELECT {SECTION_COLUMNS[table]} FROM _analysis.{table} "
                    "WHERE result_id IN :ids"
                ).bindparams(bindparam("ids", expanding=True))
                rows = (await connection.execute(statement, {"ids": ids})).mappings()
                for row in rows:
                    sections[cast(UUID, row["result_id"])].setdefault(table, []).append(
                        dict(row)
                    )
        return [StoredAnalysis(row, sections[cast(UUID, row["id"])]) for row in headers]

    async def list(self, query: AnalysisSearchParams) -> list[StoredAnalysis]:
        clauses, params = [], {"limit": query.page_size + 1}
        parameters: dict[str, object] = dict(params)
        if query.ticker is not None:
            clauses.append("ticker = :ticker")
            parameters["ticker"] = query.ticker
        if query.cursor is not None:
            clauses.append("(created_at, id) < (:created_at, :id)")
            parameters.update(created_at=query.cursor.created_at, id=query.cursor.id)
        if query.ratings is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM _analysis.portfolio_decisions p "
                "WHERE p.result_id=a.id AND p.rating IN :ratings)"
            )
            parameters["ratings"] = query.ratings
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        source = "_analysis.analysis_results"
        prefix = ""
        if query.view != "history":
            prefix = (
                f"WITH winners AS (SELECT DISTINCT ON (ticker) {HEADER_COLUMNS} "
                "FROM _analysis.analysis_results "
                "ORDER BY ticker, created_at DESC, id DESC) "
            )
            source = "winners"
        statement = text(
            prefix + f"SELECT {HEADER_COLUMNS} FROM {source} a {where} "
            "ORDER BY created_at DESC, id DESC LIMIT :limit"
        )
        if query.ratings is not None:
            statement = statement.bindparams(bindparam("ratings", expanding=True))
        async with self.read() as connection:
            rows = (await connection.execute(statement, parameters)).mappings().all()
            headers = [cast(Mapping[str, object], dict(row)) for row in rows]
            return await self.load(connection, headers, SUMMARY_TABLES)

    async def get(self, analysis_id: UUID) -> StoredAnalysis | None:
        async with self.read() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            f"SELECT {HEADER_COLUMNS} FROM _analysis.analysis_results "
                            "WHERE id=:id"
                        ),
                        {"id": analysis_id},
                    )
                )
                .mappings()
                .all()
            )
            headers = [cast(Mapping[str, object], dict(row)) for row in rows]
            loaded = await self.load(connection, headers, tuple(SECTION_MODELS))
            return loaded[0] if loaded else None

    async def ready(self) -> None:
        async with self.read() as connection:
            tables = {"analysis_results": HEADER_COLUMNS, **SECTION_COLUMNS}
            for table, columns in tables.items():
                await connection.execute(
                    text(f"SELECT {columns} FROM _analysis.{table} LIMIT 0")
                )
