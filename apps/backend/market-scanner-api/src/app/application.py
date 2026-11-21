"""Lifecycle and HTTP concerns for the independent consultation service."""

import json
import logging
import re
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.config.settings import Settings
from app.database import create_engine
from app.dependencies import get_repository
from app.http_policy import ReadHTTPPolicy, install_head_schema
from app.repositories.market_scan_repository import MarketScanRepository
from app.repositories.scan_reader import ScanReader
from app.routes.market_scans import router
from app.schemas.report import REPORT_SCHEMA
from app.utils.error import AppError, ErrorCode, InvalidArgumentError
from app.utils.logging_messages import LoggingMessages

logger = logging.getLogger("market_scanner_api")

FRAMEWORK_ERRORS = {404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED}


def error_response(error: AppError, status_code: int | None = None) -> JSONResponse:
    """Serialize a known failure as the public envelope with its HTTP status."""
    return JSONResponse(error.to_dict(), status_code=status_code or error.status_code)


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

    _install_middleware(application, configuration)

    _install_error_handlers(application)

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

    application.add_middleware(ReadHTTPPolicy)
    install_head_schema(application)
    return application


def _install_middleware(application: FastAPI, configuration: Settings) -> None:
    @application.middleware("http")
    async def authorize_and_correlate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", supplied) else uuid4().hex
        )
        request.state.request_id = request_id
        expected = "Bearer " + configuration.API_TOKEN.get_secret_value()
        if (
            request.url.path != "/health"
            and configuration.AUTH_MODE == "token"
            and not secrets.compare_digest(
                request.headers.get("Authorization", "").encode(), expected.encode()
            )
        ):
            response: Response = error_response(AppError(ErrorCode.UNAUTHENTICATED))
            response.headers["WWW-Authenticate"] = "Bearer"
        else:
            try:
                response = await call_next(request)
            except Exception as error:
                # Last HTTP boundary: never log exception text or sensitive locals.
                logger.error(
                    LoggingMessages.STRUCTURED_EVENT,
                    json.dumps(
                        {
                            "event": LoggingMessages.HTTP_UNEXPECTED_ERROR,
                            "request_id": request_id,
                            "error_type": type(error).__name__,
                        }
                    ),
                )
                response = error_response(AppError(ErrorCode.INTERNAL_ERROR))
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        return response


def _install_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        code = FRAMEWORK_ERRORS.get(error.status_code, ErrorCode.REQUEST_FAILED)
        response = error_response(AppError(code), error.status_code)
        response.headers.update(error.headers or {})
        return response

    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        return error_response(InvalidArgumentError())

    @application.exception_handler(AppError)
    async def application_error(request: Request, error: AppError) -> JSONResponse:
        if error.status_code >= 500:
            # Details hold categories and field paths only, never stored values.
            logger.warning(
                LoggingMessages.STRUCTURED_EVENT,
                json.dumps(
                    {
                        "event": LoggingMessages.HTTP_APPLICATION_ERROR,
                        "request_id": request.state.request_id,
                        "error_code": error.error_code.name,
                        "details": error.details,
                    }
                ),
            )
        return error_response(error)
