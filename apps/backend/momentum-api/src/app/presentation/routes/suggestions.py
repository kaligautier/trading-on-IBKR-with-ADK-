"""Original DeepCopy intake/status routes; no review or execution endpoint."""

import hashlib
import hmac
import re
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import Settings
from app.domain.suggestions import CurrentAnalysisExistsError, SuggestionRateLimitError
from app.presentation.http.problems import APIError
from app.services.suggestion_service import SuggestionService

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default="", max_length=500)


class SuggestionResponse(BaseModel):
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None


def caller(request: Request) -> str:
    settings: Settings = request.app.state.settings
    secret = settings.SUGGESTION_HASH_SECRET.get_secret_value()
    if not secret:
        raise APIError(503, "configuration-error")
    claims = request.headers.getlist("x-momentum-caller")
    signatures = request.headers.getlist("x-momentum-signature")
    if len(claims) != 1 or len(signatures) != 1:
        raise APIError(403, "forbidden")
    claim, signature = claims[0], signatures[0]
    if not re.fullmatch(r"[0-9a-f]{64}", claim) or not re.fullmatch(
        r"[0-9a-f]{64}", signature
    ):
        raise APIError(403, "forbidden")
    expected = hmac.new(secret.encode(), claim.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise APIError(403, "forbidden")
    return claim


@router.post(
    "",
    status_code=202,
    response_model=SuggestionResponse,
    operation_id="submit_suggestion",
)
async def submit(payload: SuggestionRequest, request: Request) -> SuggestionResponse:
    if request.query_params:
        raise APIError(400, "invalid-argument")
    identity = caller(request)
    service: SuggestionService = request.app.state.suggestions
    try:
        value = await service.submit(payload.symbol, payload.reason or "", identity)
    except CurrentAnalysisExistsError as error:
        raise APIError(409, "current-analysis") from error
    except SuggestionRateLimitError as error:
        raise APIError(429, "suggestion-quota") from error
    except ValueError as error:
        raise APIError(400, "invalid-argument") from error
    return SuggestionResponse(**asdict(value))


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
