"""Shared bounded JSON transport; API routes and DTOs belong to each client."""

import asyncio
import logging

import httpx
from pydantic import BaseModel, ValidationError

from app.api.config import ApiSettings
from app.api.errors import UpstreamError

logger = logging.getLogger(__name__)


class JsonApiClient:
    def __init__(self, client: httpx.AsyncClient, settings: ApiSettings, name: str):
        self._client = client
        self._settings = settings
        self._name = name

    async def get[Model: BaseModel](self, path: str, model: type[Model]) -> Model:
        try:
            async with asyncio.timeout(self._settings.request_timeout_seconds):
                return await self._get(path, model)
        except (httpx.TimeoutException, TimeoutError):
            raise UpstreamError(f"{self._name} API timed out") from None
        except httpx.HTTPError:
            raise UpstreamError(f"{self._name} API unavailable") from None

    async def _get[Model: BaseModel](self, path: str, model: type[Model]) -> Model:
        async with self._client.stream("GET", path) as response:
            status = response.status_code
            if status != 200:
                reasons = {
                    400: "invalid request",
                    404: "item not found",
                    401: "rejected credentials",
                    403: "rejected credentials",
                    429: "rate limit exceeded",
                    503: "not ready",
                }
                # Never log URLs, credentials, response bodies or HTTP exceptions.
                logger.warning(
                    "API request failed", extra={"api": self._name, "status": status}
                )
                raise UpstreamError(
                    f"{self._name} API: {reasons.get(status, 'unavailable')}"
                )
            if (
                response.headers.get("content-encoding", "identity").lower()
                != "identity"
            ):
                raise UpstreamError(f"{self._name} API returned unsupported encoding")
            data = bytearray()
            async for chunk in response.aiter_raw(chunk_size=8192):
                if len(data) + len(chunk) > self._settings.max_response_bytes:
                    raise UpstreamError(f"{self._name} API response too large")
                data.extend(chunk)
            try:
                return model.model_validate_json(data)
            except ValidationError:
                raise UpstreamError(f"{self._name} API returned invalid data") from None
