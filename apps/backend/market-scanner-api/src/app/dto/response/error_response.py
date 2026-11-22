"""Public AIP-193 error body and its OpenAPI documentation, from ``error.py``."""

from typing import Any

from pydantic import BaseModel

from app.utils.error import (
    CANONICAL_CODES,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    ErrorCode,
)


class ErrorStatus(BaseModel):
    """``google.rpc.Status`` in its AIP-193 HTTP/1.1+JSON representation."""

    code: int
    message: str
    status: str
    details: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: ErrorStatus


def error_responses(*codes: ErrorCode) -> dict[int | str, dict[str, Any]]:
    """Document each HTTP status once, listing every error code it can carry."""
    descriptions: dict[int, list[str]] = {}
    for code in codes:
        descriptions.setdefault(HTTP_STATUS_CODES[code], []).append(
            f"`{code.name}` ({CANONICAL_CODES[code].name}): {ERROR_MESSAGES[code]}"
        )
    return {
        status_code: {"model": ErrorResponse, "description": "; ".join(lines)}
        for status_code, lines in sorted(descriptions.items())
    }
