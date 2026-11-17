"""Consultation use cases, independent of HTTP and database connection ownership."""

from uuid import UUID

from app.domain.analyses.errors import AnalysisNotFoundError
from app.domain.analyses.models import AnalysisDetail, AnalysisPage
from app.domain.analyses.search import AnalysisSearchParams, Cursor
from app.ports.analysis_reader import AnalysisReader


class AnalysisService:
    def __init__(self, repository: AnalysisReader) -> None:
        self.repository = repository

    async def list(self, query: AnalysisSearchParams) -> AnalysisPage:
        batch = await self.repository.list(query)
        items = batch.items
        token = ""
        if batch.has_more:
            last = items[-1]
            token = Cursor(
                created_at=last.created_at, id=last.id, scope=query.scope
            ).encode()
        return AnalysisPage(items=items, next_page_token=token)

    async def get(self, analysis_id: UUID) -> AnalysisDetail:
        stored = await self.repository.get(analysis_id)
        if stored is None:
            raise AnalysisNotFoundError()
        return stored

    async def ready(self) -> None:
        await self.repository.ready()
