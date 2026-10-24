"""Uvicorn factory; configuration and connection ownership begin at startup."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.postgresql.connection import create_engine
from app.adapters.postgresql.repository import AnalysisRepository
from app.adapters.postgresql.suggestions import SuggestionRepository
from app.app_factory import create_app as application
from app.config.settings import Settings
from app.observability import LOGGER, log_event
from app.services.analysis_service import AnalysisService
from app.services.suggestion_service import SuggestionService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    # Handler.handleError must not print raw exception chains on stderr.
    logging.raiseExceptions = False
    LOGGER.setLevel(logging.INFO)
    if not LOGGER.handlers:
        LOGGER.addHandler(logging.StreamHandler())
    LOGGER.propagate = False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.service = AnalysisService(AnalysisRepository(engine))
        app.state.suggestions = SuggestionService(SuggestionRepository(engine))
        try:
            yield
        except BaseException:
            try:
                await engine.dispose()
            except Exception as error:
                log_event(
                    logging.ERROR,
                    "storage_cleanup_failed",
                    exception_type=type(error).__name__,
                )
            raise
        else:
            await engine.dispose()

    return application(settings, lifespan=lifespan)
