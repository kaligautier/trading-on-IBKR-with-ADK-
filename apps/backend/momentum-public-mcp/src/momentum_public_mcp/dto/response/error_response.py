"""Public AIP-193 HTTP error body, derived from ``utils/error.py``."""

from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from momentum_public_mcp.observability import request_event
from momentum_public_mcp.utils.error import AppError, ErrorCode

FRAMEWORK_ERRORS = {404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED}


class ErrorStatus(BaseModel):
    """``google.rpc.Status`` in its HTTP/1.1+JSON representation."""

    code: int = Field(description="HTTP status of the response.")
    message: str = Field(description="Developer-facing English message.")
    status: str = Field(description="Canonical google.rpc.Code name.")
    details: list[dict] = Field(description="ErrorInfo, then optional RequestInfo.")


class ErrorResponse(BaseModel):
    error: ErrorStatus


def error_response(
    error: AppError,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Serialize a known failure as an AIP-193 body with its HTTP status."""
    event = request_event.get()
    request_id = event["correlation_id"] if event else None
    return JSONResponse(
        error.to_status(request_id),
        status_code=error.status_code,
        headers=headers,
    )


async def http_error(_request: Request, error: Exception) -> JSONResponse:
    """Starlette routing errors outside MCP dispatch use the AIP-193 body."""
    assert isinstance(error, HTTPException)
    code = FRAMEWORK_ERRORS.get(error.status_code, ErrorCode.REQUEST_FAILED)
    failure = AppError(code, status_code=error.status_code)
    return error_response(failure, dict(error.headers or {}))
