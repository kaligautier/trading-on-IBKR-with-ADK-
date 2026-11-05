"""Cloud Run identity headers shared by the API clients."""

from typing import Protocol

import httpx
from pydantic import SecretStr

from app.api.errors import ServiceIdentityError


def backend_headers(token: SecretStr, *, use_iam: bool) -> dict[str, str]:
    """Send the API's local bearer credential only when Cloud Run IAM is disabled."""
    if use_iam or not token.get_secret_value():
        return {}
    return {"Authorization": f"Bearer {token.get_secret_value()}"}


class IdentityTokenProvider(Protocol):
    async def token(self) -> str | None: ...


class DisabledIdentityTokenProvider:
    async def token(self) -> str | None:
        return None


class MetadataIdentityTokenProvider:
    """Obtain a Google-signed ID token for a private API."""

    _ENDPOINT = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity"
    )

    def __init__(self, client: httpx.AsyncClient, audience: str):
        self._client = client
        self._audience = audience

    async def token(self) -> str:
        try:
            response = await self._client.get(
                self._ENDPOINT,
                params={"audience": self._audience, "format": "full"},
                headers={"Metadata-Flavor": "Google"},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ServiceIdentityError() from error
        token = response.text.strip()
        if token:
            return token
        raise ServiceIdentityError()


class CloudRunIdentityHeaders:
    """Build the Cloud Run edge-authentication header for API requests."""

    def __init__(self, token_provider: IdentityTokenProvider):
        self._token_provider = token_provider

    async def values(self) -> dict[str, str]:
        token = await self._token_provider.token()
        if token is None:
            return {}
        return {"X-Serverless-Authorization": f"Bearer {token}"}


def create_identity_headers(
    client: httpx.AsyncClient, audience: str, *, use_iam: bool
) -> CloudRunIdentityHeaders:
    provider = (
        MetadataIdentityTokenProvider(client, audience)
        if use_iam
        else DisabledIdentityTokenProvider()
    )
    return CloudRunIdentityHeaders(provider)
