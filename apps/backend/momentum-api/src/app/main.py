"""Uvicorn factory; configuration and connection ownership begin at startup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application import create_app as application
from app.config import Settings
from app.database import create_engine
from app.repository import AnalysisRepository
from app.service import AnalysisService


def create_app() -> FastAPI:
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.service = AnalysisService(AnalysisRepository(engine))
        try:
            yield
        finally:
            await engine.dispose()

    return application(settings, lifespan=lifespan)
