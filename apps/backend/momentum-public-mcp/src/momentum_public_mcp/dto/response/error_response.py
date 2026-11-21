"""Public HTTP error envelope, derived from ``utils/error.py`` (as in #372)."""

from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from momentum_public_mcp.utils.error import AppError, ErrorCode

FRAMEWORK_ERRORS = {404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED}


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(
    error: AppError,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Serialize a known failure as the public envelope with its HTTP status."""
    return JSONResponse(
        error.to_response(),
        status_code=status_code or error.status_code,
        headers=headers,
    )


async def http_error(_request: Request, error: Exception) -> JSONResponse:
    """Starlette routing errors outside MCP dispatch use the envelope."""
    assert isinstance(error, HTTPException)
    code = FRAMEWORK_ERRORS.get(error.status_code, ErrorCode.REQUEST_FAILED)
    return error_response(AppError(code), error.status_code, dict(error.headers or {}))
