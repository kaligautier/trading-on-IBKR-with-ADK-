"""Read-only resources backed by the public reader APIs."""

from fastmcp.exceptions import ResourceError
from fastmcp.resources import resource

from momentum_public_mcp.config.constants import (
    MARKET_SCANNER_API_PREFIX,
    MARKET_SCANNER_API_VERSION,
)
from momentum_public_mcp.mcp.gateway import MomentumApiError, MomentumPublicGateway

_LOCAL_MARKET_SCAN_URI = "momentum://market-scans/latest"
LATEST_MARKET_SCAN_URI = "momentum://market_scanner/market-scans/latest"


class MomentumPublicResources:
    def __init__(self, gateway: MomentumPublicGateway):
        self._gateway = gateway

    @resource(
        _LOCAL_MARKET_SCAN_URI,
        name="latest_market_scan",
        title="Latest market scan",
        mime_type="application/json",
        tags={"public", "market"},
        version=MARKET_SCANNER_API_VERSION,
        meta={
            "upstream": {
                "api": "market_scanner",
                "api_version": MARKET_SCANNER_API_VERSION,
                "method": "GET",
                "path": f"{MARKET_SCANNER_API_PREFIX}/market-scans/latest",
            }
        },
    )
    async def latest_market_scan(self) -> str:
        """Read the latest published scan without starting a new scan."""
        try:
            scan = await self._gateway.latest_market_scan()
        except MomentumApiError as error:
            raise ResourceError(str(error)) from error
        return scan.model_dump_json()
