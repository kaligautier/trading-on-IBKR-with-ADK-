"""Uvicorn factory; configuration and connection ownership begin at startup."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.postgresql.connection import create_engine
from app.adapters.postgresql.repository import AnalysisRepository
from app.app_factory import create_app as application
from app.config.settings import Settings
from app.presentation.http.middleware import LOGGER
from app.services.analysis_service import AnalysisService


def create_app() -> FastAPI:
    settings = Settings()
    LOGGER.setLevel(logging.INFO)
    if not LOGGER.handlers:
        LOGGER.addHandler(logging.StreamHandler())
    LOGGER.propagate = False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.service = AnalysisService(AnalysisRepository(engine))
        try:
            yield
        finally:
            await engine.dispose()

    return application(settings, lifespan=lifespan)
