"""FastAPI application factory."""

import logging
import secrets
from collections.abc import Mapping
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.cli.fast_api import get_fast_api_app
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings
from app.jobs.scheduled_scan import run_scheduled_scan
from app.middleware.wide_event import WideEventMiddleware
from app.services.database import close_database
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
        """Execute both ADK calls inside one authenticated Scheduler request."""
        if not settings.DATABASE_URL:
            return JSONResponse(
                {"detail": "Database persistence is not configured"}, status_code=503
            )
        headers = (
            {"X-Market-Scanner-Token": settings.MARKET_SCANNER_TOKEN}
            if settings.MARKET_SCANNER_TOKEN
            else {}
        )
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://adk-internal"
            ) as client:
                result = await run_scheduled_scan(client, headers)
        except Exception as error:
            logger.error(
                "scheduled scan failed",
                extra={
                    "event": "scheduled_scan.failed",
                    "error_type": type(error).__name__,
                },
            )
            return JSONResponse({"detail": "Scheduled scan failed"}, status_code=502)
        logger.info(
            "scheduled scan completed",
            extra={"event": "scheduled_scan.completed", **result},
        )
        return JSONResponse(result)

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
