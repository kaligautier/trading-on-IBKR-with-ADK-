"""Read-only MCP resources backed by the public consultation APIs."""

from fastmcp.exceptions import ResourceError
from fastmcp.resources import resource

from momentum_public_mcp.errors import AppError
from momentum_public_mcp.mcp.gateway import MomentumPublicGateway

LATEST_MARKET_SCAN_URI = "momentum://market-scans/latest"


class MomentumPublicResources:
    def __init__(self, gateway: MomentumPublicGateway):
        self._gateway = gateway

    @resource(
        LATEST_MARKET_SCAN_URI,
        name="latest_market_scan",
        title="Latest market scan",
        mime_type="application/json",
        tags={"public", "market"},
    )
    async def latest_market_scan(self) -> str:
        """Read the latest published market scan without starting a new scan."""
        try:
            scan = await self._gateway.latest_market_scan()
        except AppError as error:
            raise ResourceError(str(error)) from error
        return scan.model_dump_json()
