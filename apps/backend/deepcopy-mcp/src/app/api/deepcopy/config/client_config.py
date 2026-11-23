"""Build and close the Deepcopy API client with its own credentials and pool."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.api.config import create_http_client
from app.api.deepcopy.client.deepcopy_client import DeepcopyClient
from app.api.deepcopy.config.settings import DeepcopyApiSettings


@asynccontextmanager
async def create_deepcopy_client(
    settings: DeepcopyApiSettings,
) -> AsyncGenerator[DeepcopyClient]:
    async with create_http_client(settings) as client:
        yield DeepcopyClient(client, settings)
