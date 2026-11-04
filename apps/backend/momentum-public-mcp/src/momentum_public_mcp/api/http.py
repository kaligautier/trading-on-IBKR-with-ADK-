"""Shared authenticated HTTP transport and response validation."""

import httpx
from pydantic import ValidationError

from momentum_public_mcp.api.auth import (
    CloudRunIdentityHeaders,
    DisabledIdentityTokenProvider,
)
from momentum_public_mcp.api.errors import ApiError


class ApiHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        identity_headers: CloudRunIdentityHeaders | None = None,
        *,
        error_type: type[ApiError],
    ):
        self._client = client
        self._identity_headers = identity_headers or CloudRunIdentityHeaders(
            DisabledIdentityTokenProvider()
        )
        self._error_type = error_type

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        **arguments,
    ) -> httpx.Response:
        headers = dict(arguments.pop("headers", {}))
        try:
            headers.update(await self._identity_headers.values())
            response = await self._client.request(
                method, path, headers=headers, **arguments
            )
            self._ensure_success(response)
            return response
        except httpx.HTTPError as error:
            raise self._error_type(
                f"{self._error_type.service_name} public API is unavailable."
            ) from error

    def _ensure_success(self, response: httpx.Response) -> None:
        if not response.is_error:
            return
        service = self._error_type.service_name
        messages = {
            404: f"{service} public resource not found.",
            429: f"{service} public request limit reached.",
            422: f"{service} rejected the public input.",
        }
        raise self._error_type(
            messages.get(response.status_code),
            upstream_status_code=response.status_code,
        )

    def model(self, response: httpx.Response, model_type):
        try:
            return model_type.model_validate_json(response.content)
        except ValidationError as error:
            raise self._error_type(
                f"{self._error_type.service_name} public API returned invalid data.",
                upstream_status_code=response.status_code,
            ) from error
