"""Consultation use cases, independent of HTTP and database connection ownership."""

from typing import Protocol
from uuid import UUID

from app.adapters.postgresql.mapper import (
    InvalidStoredAnalysisError,
    StoredAnalysis,
    detail,
    summary,
)
from app.domain.analyses.search import AnalysisSearchParams, Cursor
from app.presentation.dto import AnalysisDetail, AnalysisPage
from app.presentation.http.problems import APIError


class AnalysisReader(Protocol):
    async def list(self, query: AnalysisSearchParams) -> list[StoredAnalysis]: ...
    async def get(self, analysis_id: UUID) -> StoredAnalysis | None: ...
    async def ready(self) -> None: ...


class AnalysisService:
    def __init__(self, repository: AnalysisReader) -> None:
        self.repository = repository

    async def list(self, query: AnalysisSearchParams) -> AnalysisPage:
        rows = await self.repository.list(query)
        try:
            items = [summary(row) for row in rows[: query.page_size]]
        except InvalidStoredAnalysisError:
            raise APIError(500, "invalid-stored-data") from None
        token = ""
        if len(rows) > query.page_size:
            last = items[-1]
            token = Cursor(
                created_at=last.created_at, id=last.id, scope=query.scope
            ).encode()
        return AnalysisPage(items=items, next_page_token=token)

    async def get(self, analysis_id: UUID) -> AnalysisDetail:
        stored = await self.repository.get(analysis_id)
        if stored is None:
            raise APIError(404, "analysis-not-found")
        try:
            return detail(stored)
        except InvalidStoredAnalysisError:
            raise APIError(500, "invalid-stored-data") from None

    async def ready(self) -> dict[str, str]:
        await self.repository.ready()
        return {"status": "ready"}
