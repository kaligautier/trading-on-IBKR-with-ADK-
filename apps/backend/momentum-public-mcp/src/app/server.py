"""FastMCP 4 public server composition."""

from fastmcp import FastMCP
from fastmcp.server.lifespan import Lifespan
from fastmcp.server.providers import LocalProvider
from fastmcp.server.transforms import Namespace

from app.config.constants import (
    DEFAULT_LIST_PAGE_SIZE,
    MARKET_SCANNER_NAMESPACE,
    MOMENTUM_NAMESPACE,
)
from app.config.constants import (
    PUBLIC_TOOL_NAMES as PUBLIC_TOOL_NAMES,
)
from app.core_components.prompts.public_prompts import analyze_ticker
from app.core_components.resources.public_resources import MomentumPublicResources
from app.core_components.tools.public_tools import MomentumPublicTools
from app.middleware import configure_middleware
from app.observability.health import health_check
from app.security import FingerprintProvider


class MomentumPublicMcpServer:
    """Register an immutable allowlist of public capabilities."""

    def __init__(
        self,
        tools: MomentumPublicTools,
        fingerprint: FingerprintProvider | None = None,
        lifespan: Lifespan | None = None,
        *,
        resources: MomentumPublicResources,
        list_page_size: int = DEFAULT_LIST_PAGE_SIZE,
    ):
        self.server = FastMCP(
            name="Momentum Public",
            version="0.1.0",
            instructions=(
                "Consult public Momentum analyses and propose tickers for moderation. "
                "Suggestions stay pending and never start an analysis. No "
                "administrative capability is available."
            ),
            on_duplicate="error",
            lifespan=lifespan,
            mask_error_details=True,
            tasks=False,
            list_page_size=list_page_size,
        )
        momentum = LocalProvider(on_duplicate="error")
        for component in tools.components():
            momentum.add_tool(component)
        momentum.add_prompt(analyze_ticker)
        momentum.add_transform(Namespace(MOMENTUM_NAMESPACE))
        scanner = LocalProvider(on_duplicate="error")
        scanner.add_resource(resources.latest_market_scan)
        scanner.add_transform(Namespace(MARKET_SCANNER_NAMESPACE))
        self.server.add_provider(momentum)
        self.server.add_provider(scanner)
        self.server.enable(tags={"public"}, only=True)
        self._add_health_route()
        configure_middleware(self.server, fingerprint)

    def _add_health_route(self) -> None:
        route_registrar = self.server.custom_route("/health", methods=["GET"])
        route_registrar(health_check)
