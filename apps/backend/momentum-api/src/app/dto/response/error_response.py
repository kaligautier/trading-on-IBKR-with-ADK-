"""Public error envelope and its OpenAPI documentation, derived from ``error.py``."""

import json
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel

from app.utils.error import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    WIRE_CODES,
    AppError,
    ErrorCode,
)

ERROR_MEDIA_TYPE = "application/json"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_bytes(error: AppError) -> bytes:
    """Serialize the public envelope; no exception text or details are exposed."""
    return json.dumps(
        error.to_response(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def error_descriptions(*codes: ErrorCode) -> dict[int, str]:
    """Describe each HTTP status once, listing every error code it can carry."""
    selected = codes or tuple(ErrorCode)
    lines: dict[int, list[str]] = {}
    for code in selected:
        line = f"`{WIRE_CODES[code]}`: {ERROR_MESSAGES[code]}"
        status_lines = lines.setdefault(HTTP_STATUS_CODES[code], [])
        if line not in status_lines:
            status_lines.append(line)
    return {status: "; ".join(text) for status, text in sorted(lines.items())}


def error_responses(*codes: ErrorCode) -> dict[int | str, dict[str, Any]]:
    """FastAPI ``responses`` for the given codes, using the envelope model."""
    return {
        status: {"model": ErrorResponse, "description": description}
        for status, description in error_descriptions(*codes).items()
    }


ERROR_SCHEMAS: dict[str, dict[str, Any]] = {
    "ErrorDetail": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string", "description": "Stable error code."},
            "message": {"type": "string", "description": "Sanitized message."},
        },
    },
    "ErrorResponse": {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {"$ref": "#/components/schemas/ErrorDetail"}},
        "description": "Absent when application/json is unacceptable. "
        "Missing credentials produce a bodyless Bearer challenge.",
    },
}


def status_phrase(status: int) -> str:
    """Keep the public contract stable across Python 3.12 and newer runtimes."""
    return "Content Too Large" if status == 413 else HTTPStatus(status).phrase
