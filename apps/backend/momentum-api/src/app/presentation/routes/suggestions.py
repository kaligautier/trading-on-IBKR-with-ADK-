"""Read the moderation status of an existing ticker suggestion."""

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.presentation.http.problems import APIError
from app.services.suggestion_service import SuggestionService

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionResponse(BaseModel):
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None


@router.get(
    "/{suggestion_id}", response_model=SuggestionResponse, operation_id="get_suggestion"
)
async def status(suggestion_id: UUID, request: Request) -> SuggestionResponse:
    if request.query_params:
        raise APIError(400, "invalid-argument")
    service: SuggestionService = request.app.state.suggestions
    value = await service.get(suggestion_id)
    if value is None:
        raise APIError(404, "not-found")
    return SuggestionResponse(**asdict(value))
