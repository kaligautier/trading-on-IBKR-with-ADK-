"""Versioned suggestion intake/status routes; no review or execution endpoint."""

import hashlib
import hmac
import re
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import Settings
from app.domain.suggestions import CurrentAnalysisExistsError, SuggestionRateLimitError
from app.services.suggestion_service import SuggestionService
from app.utils.error import AppError, ErrorCode, InvalidArgumentError

router = APIRouter(prefix="/v1/suggestions", tags=["suggestions"])


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
        raise AppError(ErrorCode.STORE_CONFIGURATION_ERROR, status_code=503)
    claims = request.headers.getlist("x-momentum-caller")
    signatures = request.headers.getlist("x-momentum-signature")
    if len(claims) != 1 or len(signatures) != 1:
        raise AppError(ErrorCode.FORBIDDEN)
    claim, signature = claims[0], signatures[0]
    if not re.fullmatch(r"[0-9a-f]{64}", claim) or not re.fullmatch(
        r"[0-9a-f]{64}", signature
    ):
        raise AppError(ErrorCode.FORBIDDEN)
    expected = hmac.new(secret.encode(), claim.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise AppError(ErrorCode.FORBIDDEN)
    return claim


@router.post(
    "",
    status_code=201,
    response_model=SuggestionResponse,
    operation_id="submit_suggestion",
    responses={
        200: {"model": SuggestionResponse, "description": "Existing suggestion"}
    },
)
async def submit(
    payload: SuggestionRequest, request: Request, response: Response
) -> SuggestionResponse:
    if request.query_params:
        raise InvalidArgumentError()
    identity = caller(request)
    service: SuggestionService = request.app.state.suggestions
    try:
        result = await service.submit(payload.symbol, payload.reason or "", identity)
    except CurrentAnalysisExistsError as error:
        raise AppError(ErrorCode.CURRENT_ANALYSIS_EXISTS) from error
    except SuggestionRateLimitError as error:
        raise AppError(ErrorCode.SUGGESTION_RATE_LIMIT) from error
    except ValueError as error:
        raise InvalidArgumentError() from error
    response.status_code = 201 if result.created else 200
    response.headers["Location"] = str(
        request.url_for("get_suggestion", suggestion_id=str(result.suggestion.id))
    )
    return SuggestionResponse(**asdict(result.suggestion))


@router.get(
    "/{suggestion_id}",
    response_model=SuggestionResponse,
    operation_id="get_suggestion",
    name="get_suggestion",
)
async def status(suggestion_id: UUID, request: Request) -> SuggestionResponse:
    if request.query_params:
        raise InvalidArgumentError()
    service: SuggestionService = request.app.state.suggestions
    value = await service.get(suggestion_id)
    if value is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return SuggestionResponse(**asdict(value))
