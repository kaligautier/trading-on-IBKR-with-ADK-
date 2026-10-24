"""FastMCP 4 public server composition."""

from fastmcp import FastMCP
from fastmcp.server.lifespan import Lifespan
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from starlette.responses import JSONResponse

from momentum_public_mcp.constants import PUBLIC_TOOL_NAMES  # noqa: F401 -- compatibility export
from momentum_public_mcp.observability import ToolTelemetry
from momentum_public_mcp.security import FingerprintProvider
from momentum_public_mcp.tools import MomentumPublicTools


async def health_check(request) -> JSONResponse:
    """Return process liveness without exposing application data."""
    return JSONResponse({"status": "healthy", "service": "momentum-public-mcp"})


class MomentumPublicMcpServer:
    """Register an immutable allowlist of public capabilities."""

    def __init__(
        self,
        tools: MomentumPublicTools,
        fingerprint: FingerprintProvider | None = None,
        lifespan: Lifespan | None = None,
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
        self.server.enable(tags={"public"}, only=True)
        self.server.add_middleware(ToolTelemetry())
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
