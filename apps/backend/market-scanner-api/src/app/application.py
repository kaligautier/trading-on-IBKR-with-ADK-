"""Lifecycle and HTTP concerns for the independent consultation service."""

import json
import logging
import re
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.config.settings import Settings
from app.database import create_engine
from app.dependencies import get_repository
from app.dto.response.market_scan_response_assembler import (
    REPORT_SCHEMA,
    InvalidStoredReportError,
)
from app.models.cursor import InvalidCursorError
from app.repositories.market_scan_repository import MarketScanRepository
from app.repositories.scan_reader import ScanReader, StoreUnavailableError
from app.routes.market_scans import router
from app.services.market_scan_service import ScanNotFoundError

logger = logging.getLogger("market_scanner_api")


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status
    )


def create_app(
    settings: Settings | None = None, *, repository: ScanReader | None = None
) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = None
        if repository is not None:
            application.state.repository = repository
        else:
            engine = create_engine(configuration)
            application.state.repository = MarketScanRepository(
                engine, configuration.DATABASE_SCHEMA
            )
        try:
            yield
        finally:
            if engine is not None:
                await engine.dispose()

    application = FastAPI(
        title="Market Scanner consultation API", version="1.0.0", lifespan=lifespan
    )
    application.include_router(router)

    @application.middleware("http")
    async def observe_and_authorize(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", supplied) else uuid4().hex
        )
        request.state.request_id = request_id
        start = monotonic()
        expected = "Bearer " + configuration.API_TOKEN.get_secret_value()
        if (
            request.url.path != "/health"
            and configuration.AUTH_MODE == "token"
            and not secrets.compare_digest(
                request.headers.get("Authorization", "").encode(), expected.encode()
            )
        ):
            response: Response = error_response(
                401, "UNAUTHENTICATED", "Authentication required"
            )
            response.headers["WWW-Authenticate"] = "Bearer"
        else:
            try:
                response = await call_next(request)
            except Exception as error:
                # Last HTTP boundary: never log exception text or sensitive locals.
                logger.error(
                    json.dumps(
                        {
                            "event": "http.unexpected_error",
                            "request_id": request_id,
                            "error_type": type(error).__name__,
                        }
                    )
                )
                response = error_response(
                    500, "INTERNAL_ERROR", "Internal server error"
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "event": "http.completed",
                    "request_id": request_id,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((monotonic() - start) * 1000, 2),
                }
            )
        )
        return response

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        code, message = {
            404: ("NOT_FOUND", "Route not found"),
            405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
        }.get(error.status_code, ("REQUEST_FAILED", "Request failed"))
        response = error_response(error.status_code, code, message)
        response.headers.update(error.headers or {})
        return response

    @application.exception_handler(ScanNotFoundError)
    async def missing(_request: Request, _error: ScanNotFoundError) -> JSONResponse:
        return error_response(404, "SCAN_NOT_FOUND", "No market scan available")

    @application.exception_handler(StoreUnavailableError)
    async def unavailable(
        request: Request, error: StoreUnavailableError
    ) -> JSONResponse:
        logger.warning(
            json.dumps(
                {
                    "event": "storage.unavailable",
                    "request_id": request.state.request_id,
                    "error_type": error.category,
                }
            )
        )
        return error_response(503, "STORE_UNAVAILABLE", "Scan storage is unavailable")

    @application.exception_handler(InvalidStoredReportError)
    async def invalid_report(
        _request: Request, _error: InvalidStoredReportError
    ) -> JSONResponse:
        return error_response(500, "INVALID_STORED_REPORT", "Stored report is invalid")

    @application.exception_handler(InvalidCursorError)
    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, _error: RequestValidationError | InvalidCursorError
    ) -> JSONResponse:
        return error_response(422, "INVALID_ARGUMENT", "Invalid request parameters")

    @application.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "market-scanner-api"}

    @application.get("/ready", tags=["operations"])
    async def ready(request: Request) -> dict[str, str]:
        await get_repository(request).latest()
        return {"status": "ready"}

    @application.get("/schemas/report-v3.json", tags=["contract"])
    async def report_schema() -> JSONResponse:
        return JSONResponse(REPORT_SCHEMA)

    return application
