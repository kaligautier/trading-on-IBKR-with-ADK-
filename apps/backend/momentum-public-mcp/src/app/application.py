"""Production composition root for the public MCP service."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn

from app.api.market_scanner.config.client_config import (
    create_market_scanner_client,
)
from app.api.momentum.config.client_config import create_momentum_client
from app.config.config import Settings
from app.core_components.gateway import MomentumHttpGateway
from app.core_components.resources.public_resources import MomentumPublicResources
from app.core_components.tools.public_tools import MomentumPublicTools
from app.protocol import create_http_app
from app.security import (
    CallerFingerprint,
    ClientAddressResolver,
    TrustedProxyNetworks,
)
from app.server import MomentumPublicMcpServer


class MomentumPublicApplication:
    """Own the HTTP client and FastMCP runtime."""

    def __init__(self, settings: Settings):
        gateway = MomentumHttpGateway(
            momentum=create_momentum_client(settings),
            scanner=create_market_scanner_client(
                settings, use_iam=settings.MOMENTUM_API_USE_IAM
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

        self.mcp = MomentumPublicMcpServer(
            tools,
            fingerprint,
            lifespan,
            resources=MomentumPublicResources(gateway),
            list_page_size=settings.DEFAULT_PAGE_SIZE,
        ).server

    def run(self) -> None:
        uvicorn.run(
            create_http_app(self.mcp),
            host="0.0.0.0",
            port=self._settings.PORT,
            proxy_headers=False,
            log_config=None,
            access_log=False,
        )
