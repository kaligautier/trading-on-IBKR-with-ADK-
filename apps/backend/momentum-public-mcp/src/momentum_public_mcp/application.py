"""Production composition root for the public MCP service."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import uvicorn
from pydantic import SecretStr

from momentum_public_mcp.config import Settings
from momentum_public_mcp.gateway import (
    CloudRunIdentityHeaders,
    DisabledIdentityTokenProvider,
    MetadataIdentityTokenProvider,
    MomentumHttpGateway,
    SuggestionSigner,
)
from momentum_public_mcp.observability import configure_logging
from momentum_public_mcp.protocol import create_http_app
from momentum_public_mcp.security import (
    CallerFingerprint,
    ClientAddressResolver,
    TrustedProxyNetworks,
)
from momentum_public_mcp.server import MomentumPublicMcpServer
from momentum_public_mcp.tools import MomentumPublicTools


class MomentumPublicApplication:
    """Own the HTTP client and FastMCP runtime."""

    def __init__(self, settings: Settings):
        client = httpx.AsyncClient(
            base_url=settings.MOMENTUM_API_URL,
            headers=self._backend_headers(settings, settings.MOMENTUM_API_TOKEN),
            timeout=httpx.Timeout(40, connect=5),
            follow_redirects=False,
        )
        market_scanner_client = httpx.AsyncClient(
            base_url=settings.MARKET_SCANNER_API_URL,
            headers=self._backend_headers(settings, settings.MARKET_SCANNER_API_TOKEN),
            timeout=httpx.Timeout(40, connect=5),
            follow_redirects=False,
        )
        identity_headers = CloudRunIdentityHeaders(
            self._identity_provider(settings, client)
        )
        gateway = MomentumHttpGateway(
            client,
            SuggestionSigner(settings.SUGGESTION_HASH_SECRET.get_secret_value()),
            market_scanner_client,
            identity_headers,
            CloudRunIdentityHeaders(
                MetadataIdentityTokenProvider(
                    market_scanner_client, settings.MARKET_SCANNER_API_URL
                )
                if settings.MOMENTUM_API_USE_IAM
                else DisabledIdentityTokenProvider()
            ),
        )
        resolver = ClientAddressResolver(
            TrustedProxyNetworks.from_csv(settings.TRUSTED_PROXIES)
        )
        fingerprint = CallerFingerprint(
            settings.SUGGESTION_HASH_SECRET.get_secret_value(), resolver
        )
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
    def _backend_headers(settings, token: SecretStr) -> dict[str, str]:
        if settings.MOMENTUM_API_USE_IAM or not token.get_secret_value():
            return {}
        return {"Authorization": f"Bearer {token.get_secret_value()}"}

    @staticmethod
    def _identity_provider(settings, client):
        if settings.MOMENTUM_API_USE_IAM:
            return MetadataIdentityTokenProvider(client, settings.MOMENTUM_API_URL)
        return DisabledIdentityTokenProvider()

    def run(self) -> None:
        configure_logging(self._settings.GOOGLE_CLOUD_PROJECT)
        uvicorn.run(
            create_http_app(self.mcp),
            host="0.0.0.0",
            port=self._settings.PORT,
            proxy_headers=False,
            log_config=None,
            access_log=False,
        )
