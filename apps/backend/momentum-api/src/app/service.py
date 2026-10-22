"""Consultation use cases, independent of HTTP and database connection ownership."""

from typing import Protocol

from app.assembly import InvalidStoredAnalysisError, StoredAnalysis, summary
from app.dto import AnalysisPage
from app.http.problems import APIError
from app.query import Cursor, Query


class AnalysisReader(Protocol):
    async def list(self, query: Query) -> list[StoredAnalysis]: ...


class AnalysisService:
    def __init__(self, repository: AnalysisReader) -> None:
        self.repository = repository

    async def list(self, query: Query) -> AnalysisPage:
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
