"""Shared HTTP client defaults and upstream URL validation."""

from urllib.parse import urlsplit

import httpx
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def create_http_client(
    base_url: str, *, headers: dict[str, str] | None = None
) -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=httpx.Timeout(40, connect=5),
        follow_redirects=False,
    )
    HTTPXClientInstrumentor.instrument_client(client)
    return client


def validate_api_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("API URL must be an absolute HTTP URL")
    if parsed.username or parsed.password:
        raise ValueError("API URL must not contain credentials")
    local_hosts = {
        "localhost",
        "127.0.0.1",
        "::1",
        "momentum-api",
        "market-scanner-api",
    }
    if parsed.scheme != "https" and parsed.hostname not in local_hosts:
        raise ValueError("API URL must use HTTPS outside local development")
    return value.rstrip("/")
