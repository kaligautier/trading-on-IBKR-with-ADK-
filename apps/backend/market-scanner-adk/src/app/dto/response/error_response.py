"""Public AIP-193 HTTP error body and its OpenAPI docs, derived from ``error.py``."""

from typing import Any

from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.utils.error import (
    CANONICAL_CODES,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    AppError,
    ErrorCode,
)
from app.utils.wide_event import wide_event


class ErrorStatus(BaseModel):
    """``google.rpc.Status`` in its AIP-193 HTTP/1.1+JSON representation."""

    code: int
    message: str
    status: str
    details: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: ErrorStatus


def error_response(
    error: AppError, headers: dict[str, str] | None = None
) -> JSONResponse:
    """Serialize a known failure as an AIP-193 Status with its HTTP status."""
    if error.retry_after is not None:
        headers = {"Retry-After": str(error.retry_after), **(headers or {})}
    return JSONResponse(
        error.to_status(wide_event.request_id()),
        status_code=error.status_code,
        headers=headers,
    )


def error_responses(*codes: ErrorCode) -> dict[int | str, dict[str, Any]]:
    """Document each HTTP status once, listing every error reason it can carry."""
    descriptions: dict[int, list[str]] = {}
    for code in codes:
        descriptions.setdefault(HTTP_STATUS_CODES[code], []).append(
            f"`{code.name}` ({CANONICAL_CODES[code].name}): {ERROR_MESSAGES[code]}"
        )
    return {
        status_code: {"model": ErrorResponse, "description": "; ".join(lines)}
        for status_code, lines in sorted(descriptions.items())
    }
