"""Own the configured API client for the server lifetime."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from app.api.deepcopy.config.client_config import create_deepcopy_client
from app.config.settings import Settings
from app.services.portfolio_service import PortfolioService


def api_lifespan(
    settings: Settings,
) -> Callable[[FastMCP], AbstractAsyncContextManager[dict[str, Any]]]:
    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncGenerator[dict[str, Any]]:
        async with AsyncExitStack() as stack:
            services = {}
            if settings.deepcopy_api is not None:
                deepcopy = await stack.enter_async_context(
                    create_deepcopy_client(settings.deepcopy_api)
                )
                services["portfolio"] = PortfolioService(deepcopy)
            yield services

    return lifespan
