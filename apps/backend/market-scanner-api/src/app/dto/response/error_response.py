"""Public error envelope and its OpenAPI documentation, derived from ``error.py``."""

from typing import Any

from pydantic import BaseModel

from app.utils.error import ERROR_MESSAGES, HTTP_STATUS_CODES, ErrorCode


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_responses(*codes: ErrorCode) -> dict[int | str, dict[str, Any]]:
    """Document each HTTP status once, listing every error code it can carry."""
    descriptions: dict[int, list[str]] = {}
    for code in codes:
        descriptions.setdefault(HTTP_STATUS_CODES[code], []).append(
            f"`{code.name}`: {ERROR_MESSAGES[code]}"
        )
    return {
        status_code: {"model": ErrorResponse, "description": "; ".join(lines)}
        for status_code, lines in sorted(descriptions.items())
    }
