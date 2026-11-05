"""Read-only MCP resources backed by the public consultation APIs."""

from fastmcp.exceptions import ResourceError
from fastmcp.resources import resource

from app.config.constants import MARKET_SCANNER_NAMESPACE
from app.core_components.gateway import MomentumPublicGateway
from app.errors import AppError

_LOCAL_MARKET_SCAN_URI = "momentum://market-scans/latest"
LATEST_MARKET_SCAN_URI = f"momentum://{MARKET_SCANNER_NAMESPACE}/market-scans/latest"


class MomentumPublicResources:
    def __init__(self, gateway: MomentumPublicGateway):
        self._gateway = gateway

    @resource(
        _LOCAL_MARKET_SCAN_URI,
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
