"""Schema-qualified, bounded PostgreSQL reads with no runtime migrations."""

import re
from collections.abc import Sequence
from typing import cast
from uuid import UUID

from asyncpg import PostgresError  # type: ignore[import-untyped]
from pydantic import JsonValue
from sqlalchemy import RowMapping, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.cursor import Cursor
from app.models.market_scan import ScanSummary, StoredScan
from app.repositories.scan_reader import StoreUnavailableError


class MarketScanRepository:
    def __init__(self, engine: AsyncEngine, schema: str) -> None:
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid database schema")
        self._engine = engine
        self._table = f'"{schema}".market_scans'

    async def _read(
        self, query: str, parameters: dict[str, object] | None = None
    ) -> Sequence[RowMapping]:
        try:
            async with (
                self._engine.connect() as connection,
                connection.begin(),
            ):
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                result = await connection.execute(text(query), parameters or {})
                return result.mappings().all()
        except (SQLAlchemyError, PostgresError, TimeoutError, OSError) as error:
            raise StoreUnavailableError(type(error).__name__) from None

    async def latest(self) -> StoredScan | None:
        rows = await self._read(
            f"SELECT id, scan_date, created_at, report FROM {self._table} "
            "ORDER BY created_at DESC, id DESC LIMIT 1"
        )
        return self._scan(rows[0]) if rows else None

    async def get(self, scan_id: UUID) -> StoredScan | None:
        rows = await self._read(
            f"SELECT id, scan_date, created_at, report FROM {self._table} WHERE id=:id",
            {"id": scan_id},
        )
        return self._scan(rows[0]) if rows else None

    async def list(self, page_size: int, cursor: Cursor | None) -> list[ScanSummary]:
        parameters: dict[str, object] = {"limit": page_size + 1}
        predicate = ""
        if cursor is not None:
            predicate = "WHERE (created_at, id) < (:created_at, :id) "
            parameters.update(created_at=cursor.created_at, id=cursor.id)
        rows = await self._read(
            f"SELECT id, scan_date, created_at, regime, summary FROM {self._table} "
            f"{predicate}ORDER BY created_at DESC, id DESC LIMIT :limit",
            parameters,
        )
        return [ScanSummary(**row) for row in rows]

    @staticmethod
    def _scan(row: RowMapping) -> StoredScan:
        return StoredScan(
            id=row["id"],
            scan_date=row["scan_date"],
            created_at=row["created_at"],
            report=cast(JsonValue, row["report"]),
        )
