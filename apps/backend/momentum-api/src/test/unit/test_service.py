"""Use cases operate through the reader port without HTTP or a database."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from app.app_factory import create_app
from app.config.settings import Settings
from app.domain.analyses.errors import (
    AnalysisNotFoundError,
    ConsultationError,
    InvalidStoredAnalysisError,
    StoreConfigurationError,
    StoreUnavailableError,
)
from app.domain.analyses.models import AnalysisBatch, AnalysisSummary
from app.domain.analyses.search import AnalysisSearchParams, Cursor
from app.ports.analysis_reader import AnalysisReader
from app.services.analysis_service import AnalysisService


async def test_use_case_paginates_domain_models_from_reader_port():
    reader = AsyncMock(spec=AnalysisReader)
    item = AnalysisSummary(
        id=UUID(int=1),
        ticker="AAPL",
        analysis_date=date(2026, 10, 22),
        created_at=datetime(2026, 10, 22, tzinfo=UTC),
        llm_provider="fixture",
    )
    reader.list.return_value = AnalysisBatch([item], has_more=True)
    query = AnalysisSearchParams.from_parameters("latest", "aapl", None, 1, "")
    service = AnalysisService(reader)
    page = await service.list(query)
    assert page.items == [item]
    cursor = Cursor.decode(page.next_page_token)
    assert cursor.id == item.id and cursor.scope == query.scope
    reader.list.assert_awaited_once_with(query)
    reader.get.return_value = None
    with pytest.raises(AnalysisNotFoundError) as caught:
        await service.get(UUID(int=2))
    assert not hasattr(caught.value, "status")
    await service.ready()
    reader.ready.assert_awaited_once()


@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        (AnalysisNotFoundError, 404, "ANALYSIS_NOT_FOUND"),
        (InvalidStoredAnalysisError, 500, "INVALID_STORED_ANALYSIS"),
        (StoreConfigurationError, 500, "STORE_CONFIGURATION_ERROR"),
        (StoreUnavailableError, 503, "STORE_UNAVAILABLE"),
        (ConsultationError, 500, "INTERNAL_ERROR"),
    ],
)
async def test_application_failures_are_translated_only_at_http_boundary(
    error_type, status, code
):
    app = create_app(
        Settings(
            DATABASE_URL="postgresql://momentum_results_reader:unused@localhost/momentum",
            API_TOKEN="disposable-test-token",
        )
    )

    @app.get("/failure")
    async def failure():
        raise error_type("private driver message")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/failure", headers={"Authorization": "Bearer disposable-test-token"}
        )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "private driver message" not in response.text
