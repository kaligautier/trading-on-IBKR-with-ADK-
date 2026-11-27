"""FastAPI application factory."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.cli.fast_api import get_fast_api_app

from app.config.settings import settings
from app.routes.ibkr_routes import router as ibkr_router
from app.utils.error import AppError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    # Create FastAPI app with ADK integration
    app: FastAPI = get_fast_api_app(
        agents_dir=settings.AGENT_DIR,
        web=True,  # Enable web UI
    )

    # Set application metadata
    app.title = settings.APP_NAME
    app.description = settings.APP_DESCRIPTION
    app.version = settings.APP_VERSION

    app.include_router(ibkr_router)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(content=error.to_dict(), status_code=error.status_code)

    # Add custom health check endpoint
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

    logger.info(
        f"FastAPI application created: {settings.APP_NAME} v{settings.APP_VERSION}"
    )
    logger.info(f"Agent directory: {settings.AGENT_DIR}")
    logger.info("Web UI enabled: True")

    return app
