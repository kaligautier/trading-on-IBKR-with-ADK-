"""Public AIP-193 error body and its OpenAPI documentation, from ``error.py``."""

import json
from contextvars import ContextVar
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel

from app.utils.error import (
    CANONICAL_CODES,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    AppError,
    ErrorCode,
)

ERROR_MEDIA_TYPE = "application/json"

# Set by the HTTP middleware so every error body carries its RequestInfo.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class ErrorStatus(BaseModel):
    """``google.rpc.Status`` in its AIP-193 HTTP/1.1+JSON representation."""

    code: int
    message: str
    status: str
    details: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: ErrorStatus


def error_bytes(error: AppError) -> bytes:
    """Serialize the public Status; no exception text or details are exposed."""
    return json.dumps(
        error.to_status(request_id_var.get()),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def error_descriptions(*codes: ErrorCode) -> dict[int, str]:
    """Describe each HTTP status once, listing every error code it can carry."""
    selected = codes or tuple(ErrorCode)
    lines: dict[int, list[str]] = {}
    for code in selected:
        line = f"`{code.name}` ({CANONICAL_CODES[code].name}): {ERROR_MESSAGES[code]}"
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
    "ErrorStatus": {
        "type": "object",
        "required": ["code", "message", "status", "details"],
        "description": "google.rpc.Status (Google AIP-193 HTTP/1.1+JSON).",
        "properties": {
            "code": {"type": "integer", "description": "HTTP status code."},
            "message": {"type": "string", "description": "Sanitized message."},
            "status": {
                "type": "string",
                "description": "Canonical google.rpc.Code name.",
            },
            "details": {
                "type": "array",
                "description": "ErrorInfo (reason, domain, metadata), then "
                "RequestInfo (requestId) and Help (links). Branch on "
                "ErrorInfo.reason, never on message.",
                "items": {
                    "type": "object",
                    "required": ["@type"],
                    "properties": {"@type": {"type": "string"}},
                    "additionalProperties": True,
                },
            },
        },
    },
    "ErrorResponse": {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {"$ref": "#/components/schemas/ErrorStatus"}},
        "description": "Absent when application/json is unacceptable. "
        "Missing credentials produce a bodyless Bearer challenge.",
    },
}


def status_phrase(status: int) -> str:
    """Keep the public contract stable across Python 3.12 and newer runtimes."""
    return "Content Too Large" if status == 413 else HTTPStatus(status).phrase
