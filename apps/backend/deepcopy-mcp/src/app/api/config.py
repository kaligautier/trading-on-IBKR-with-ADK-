"""Explicit connection settings for one trusted upstream API."""

from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator


class ApiSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    base_url: HttpUrl
    token: SecretStr
    request_timeout_seconds: float = Field(default=10, gt=0, le=120)
    connect_timeout_seconds: float = Field(default=3, gt=0, le=30)
    read_timeout_seconds: float = Field(default=5, gt=0, le=60)
    pool_timeout_seconds: float = Field(default=1, gt=0, le=30)
    max_connections: int = Field(default=10, ge=1, le=100)
    max_response_bytes: int = Field(default=65536, ge=1, le=1048576)

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        url = self.base_url
        if (
            url.username
            or url.password
            or url.query is not None
            or url.fragment is not None
        ):
            raise ValueError("API URL must not include credentials, query or fragment")
        token = self.token.get_secret_value()
        if not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise ValueError("API token must contain only visible ASCII without spaces")
        return self


def create_http_client(settings: ApiSettings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=str(settings.base_url).rstrip("/") + "/",
        headers={
            "Authorization": f"Bearer {settings.token.get_secret_value()}",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
        timeout=httpx.Timeout(
            settings.read_timeout_seconds,
            connect=settings.connect_timeout_seconds,
            pool=settings.pool_timeout_seconds,
        ),
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_connections,
        ),
        follow_redirects=False,
        trust_env=False,
    )
