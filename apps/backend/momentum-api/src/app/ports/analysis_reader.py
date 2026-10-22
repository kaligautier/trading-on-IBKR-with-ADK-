"""Read capabilities required by consultation use cases."""

from typing import Protocol
from uuid import UUID

from app.domain.analyses.models import AnalysisBatch, AnalysisDetail
from app.domain.analyses.search import AnalysisSearchParams


class AnalysisReader(Protocol):
    async def list(self, query: AnalysisSearchParams) -> AnalysisBatch: ...
    async def get(self, analysis_id: UUID) -> AnalysisDetail | None: ...
    async def ready(self) -> None: ...
