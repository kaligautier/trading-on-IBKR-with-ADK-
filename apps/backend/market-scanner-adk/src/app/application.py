"""FastAPI application factory."""

import asyncio
import logging
import secrets
from collections.abc import Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.cli.fast_api import get_fast_api_app
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings
from app.middleware.wide_event import WideEventMiddleware
from app.services.database import close_database
from app.services.scan_dispatch import dispatch_scan
from app.utils.error import AppError
from app.utils.wide_event import wide_event

logger = logging.getLogger(__name__)


class ScannerRouteAuthorizer:
    """Authorize protected scanner routes independently from Cloud Run IAM."""

    def __init__(self, token: str) -> None:
        self._token = token

    def is_authorized(self, headers: Mapping[str, str]) -> bool:
        if not self._token:
            return True
        dedicated_token = headers.get("X-Market-Scanner-Token", "")
        if secrets.compare_digest(dedicated_token, self._token):
            return True
        bearer_token = headers.get("Authorization", "")
        return secrets.compare_digest(bearer_token, f"Bearer {self._token}")


class ScannerAuthMiddleware:
    """Protect HTTP and WebSocket ADK routes with the configured token."""

    def __init__(self, app: ASGIApp, authorizer: ScannerRouteAuthorizer) -> None:
        self.app = app
        self.authorizer = authorizer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] in {"http", "websocket"}
            and _requires_token(scope["path"])
            and not self.authorizer.is_authorized(Headers(scope=scope))
        ):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await JSONResponse({"detail": "Unauthorized"}, status_code=401)(
                    scope, receive, send
                )
            return
        await self.app(scope, receive, send)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    authorizer = ScannerRouteAuthorizer(settings.MARKET_SCANNER_TOKEN)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            await close_database()

    app: FastAPI = get_fast_api_app(
        agents_dir=settings.AGENT_DIR,
        web=True,
        lifespan=lifespan,
        allow_origins=settings.ADK_ALLOW_ORIGINS,
    )

    app.title = settings.APP_NAME
    app.description = settings.APP_DESCRIPTION
    app.version = settings.APP_VERSION

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, error: AppError):
        wide_event.add(
            **{
                "error.kind": type(error).__name__,
                "error.code": error.error_code.name,
                "error.details": error.details,
            }
        )
        if error.status_code >= 500:
            logger.warning("%s", error)
        return JSONResponse(
            status_code=error.status_code, content={"error": error.message}
        )

    app.add_middleware(ScannerAuthMiddleware, authorizer=authorizer)
    app.add_middleware(WideEventMiddleware)

    @app.get("/health", tags=["Health"], summary="Health Check")
    async def health_check():
        """
        Health check endpoint for monitoring systems.

        Returns:
            JSONResponse: A simple JSON response with status "ok"
        """
        return JSONResponse(
            content={
                "status": "ok",
                "app": settings.APP_NAME,
                "version": settings.APP_VERSION,
            },
            status_code=200,
        )

    @app.post("/internal/daily-scan", tags=["Operations"])
    async def daily_scan() -> JSONResponse:
        """Acknowledge job submission without waiting for the scan."""
        if not settings.MARKET_SCANNER_JOB:
            return JSONResponse(
                {"detail": "Scheduled scan job is not configured"}, status_code=503
            )
        try:
            operation = await asyncio.to_thread(
                dispatch_scan, settings.MARKET_SCANNER_JOB
            )
        except Exception as error:
            logger.error(
                "scheduled scan dispatch failed",
                extra={
                    "event": "scheduled_scan.dispatch_failed",
                    "error_type": type(error).__name__,
                },
            )
            return JSONResponse(
                {"detail": "Scheduled scan dispatch failed"}, status_code=502
            )
        logger.info(
            "scheduled scan accepted",
            extra={"event": "scheduled_scan.accepted", "operation": operation},
        )
        return JSONResponse({"status": "accepted", "operation": operation})

    logger.info(
        "application created",
        extra={
            "event": "application.created",
            "app.name": settings.APP_NAME,
            "app.version": settings.APP_VERSION,
            "agent.directory": settings.AGENT_DIR,
            "web.enabled": True,
        },
    )

    return app


def _requires_token(path: str) -> bool:
    return path != "/health"
