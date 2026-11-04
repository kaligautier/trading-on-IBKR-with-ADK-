"""FastMCP 4 public server composition."""

from fastmcp import FastMCP
from fastmcp.server.lifespan import Lifespan
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware

from momentum_public_mcp.config.constants import PUBLIC_TOOL_NAMES  # noqa: F401 -- compatibility export
from momentum_public_mcp.mcp.prompts.public_prompts import analyze_ticker
from momentum_public_mcp.mcp.resources.public_resources import MomentumPublicResources
from momentum_public_mcp.mcp.tools.public_tools import MomentumPublicTools
from momentum_public_mcp.observability.health import health_check
from momentum_public_mcp.security import FingerprintProvider


class MomentumPublicMcpServer:
    """Register an immutable allowlist of public capabilities."""

    def __init__(
        self,
        tools: MomentumPublicTools,
        fingerprint: FingerprintProvider | None = None,
        lifespan: Lifespan | None = None,
        *,
        resources: MomentumPublicResources,
    ):
        self.server = FastMCP(
            name="Momentum Public",
            version="0.1.0",
            instructions=(
                "Consult public Momentum analyses and propose tickers for moderation. "
                "Suggestions stay pending and never start an analysis. No "
                "administrative capability is available."
            ),
            tools=tools.components(),
            on_duplicate="error",
            lifespan=lifespan,
            mask_error_details=True,
            tasks=False,
        )
        self.server.add_resource(resources.latest_market_scan)
        self.server.add_prompt(analyze_ticker)
        self.server.enable(tags={"public"}, only=True)
        self._add_health_route()
        if fingerprint is not None:
            self._add_rate_limit(fingerprint)

    def _add_rate_limit(self, fingerprint: FingerprintProvider) -> None:
        middleware = SlidingWindowRateLimitingMiddleware(
            max_requests=60,
            window_minutes=1,
            get_client_id=lambda context: fingerprint.current(),
        )
        self.server.add_middleware(middleware)

    def _add_health_route(self) -> None:
        route_registrar = self.server.custom_route("/health", methods=["GET"])
        route_registrar(health_check)
