"""Production composition root for the public MCP service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import uvicorn

from momentum_public_mcp.gateway import (
    CloudRunIdentityHeaders,
    DisabledIdentityTokenProvider,
    MetadataIdentityTokenProvider,
    MomentumHttpGateway,
    SuggestionSigner,
)
from momentum_public_mcp.protocol import create_http_app
from momentum_public_mcp.security import (
    CallerFingerprint,
    ClientAddressResolver,
    TrustedProxyNetworks,
)
from momentum_public_mcp.server import MomentumPublicMcpServer
from momentum_public_mcp.tools import MomentumPublicTools


@dataclass(frozen=True, slots=True)
class MomentumPublicSettings:
    """Validated runtime configuration."""

    api_url: str
    market_scanner_api_url: str
    suggestion_hash_secret: str
    trusted_proxies: TrustedProxyNetworks
    use_cloud_run_identity: bool
    port: int

    @classmethod
    def from_environment(cls) -> MomentumPublicSettings:
        api_url = os.environ.get("MOMENTUM_API_URL", "http://localhost:8000")
        market_scanner_api_url = os.environ.get(
            "MARKET_SCANNER_API_URL", "http://localhost:8003"
        )
        secret = os.environ.get("SUGGESTION_HASH_SECRET", "")
        proxies = TrustedProxyNetworks.from_csv(os.environ.get("TRUSTED_PROXIES", ""))
        use_cloud_run_identity = cls._boolean("MOMENTUM_API_USE_IAM", False)
        port = cls._port(os.environ.get("PORT", "8080"))
        cls._validate_api_url(api_url)
        cls._validate_api_url(market_scanner_api_url)
        if not secret:
            raise RuntimeError("SUGGESTION_HASH_SECRET is required.")
        return cls(
            api_url.rstrip("/"),
            market_scanner_api_url.rstrip("/"),
            secret,
            proxies,
            use_cloud_run_identity,
            port,
        )

    @staticmethod
    def _boolean(name: str, default: bool) -> bool:
        raw_value = os.environ.get(name, str(default)).strip().lower()
        if raw_value in {"true", "1", "yes"}:
            return True
        if raw_value in {"false", "0", "no"}:
            return False
        raise RuntimeError(f"{name} must be true or false.")

    @staticmethod
    def _port(raw_port: str) -> int:
        try:
            port = int(raw_port)
        except ValueError as error:
            raise RuntimeError("PORT must be an integer.") from error
        if 1 <= port <= 65535:
            return port
        raise RuntimeError("PORT must be between 1 and 65535.")

    @staticmethod
    def _validate_api_url(api_url: str) -> None:
        parsed_url = urlsplit(api_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise RuntimeError("Public API URL must be an absolute HTTP URL.")
        if parsed_url.username or parsed_url.password:
            raise RuntimeError("Public API URL must not contain credentials.")
        local_hosts = {
            "localhost",
            "127.0.0.1",
            "::1",
            "momentum-api",
            "market-scanner-api",
        }
        if parsed_url.scheme == "https" or parsed_url.hostname in local_hosts:
            return
        raise RuntimeError("Public API URL must use HTTPS outside local development.")


class MomentumPublicApplication:
    """Own the HTTP client and FastMCP runtime."""

    def __init__(self, settings: MomentumPublicSettings):
        client = httpx.AsyncClient(
            base_url=settings.api_url,
            timeout=httpx.Timeout(40, connect=5),
            follow_redirects=False,
        )
        market_scanner_client = httpx.AsyncClient(
            base_url=settings.market_scanner_api_url,
            timeout=httpx.Timeout(40, connect=5),
            follow_redirects=False,
        )
        identity_headers = CloudRunIdentityHeaders(
            self._identity_provider(settings, client)
        )
        gateway = MomentumHttpGateway(
            client,
            SuggestionSigner(settings.suggestion_hash_secret),
            market_scanner_client,
            identity_headers,
            CloudRunIdentityHeaders(
                MetadataIdentityTokenProvider(
                    market_scanner_client, settings.market_scanner_api_url
                )
                if settings.use_cloud_run_identity
                else DisabledIdentityTokenProvider()
            ),
        )
        resolver = ClientAddressResolver(settings.trusted_proxies)
        fingerprint = CallerFingerprint(settings.suggestion_hash_secret, resolver)
        tools = MomentumPublicTools(gateway, fingerprint)
        self._settings = settings
        self._gateway = gateway

        @asynccontextmanager
        async def lifespan(server):
            try:
                yield {}
            finally:
                await gateway.close()

        self.mcp = MomentumPublicMcpServer(tools, fingerprint, lifespan).server

    @staticmethod
    def _identity_provider(settings, client):
        if settings.use_cloud_run_identity:
            return MetadataIdentityTokenProvider(client, settings.api_url)
        return DisabledIdentityTokenProvider()

    def run(self) -> None:
        uvicorn.run(
            create_http_app(self.mcp),
            host="0.0.0.0",
            port=self._settings.port,
            proxy_headers=False,
        )
