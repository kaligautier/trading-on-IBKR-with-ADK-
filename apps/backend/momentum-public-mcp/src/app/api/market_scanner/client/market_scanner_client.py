"""HTTP client for the Market Scanner consultation API."""

import httpx

from app.api.auth import CloudRunIdentityHeaders
from app.api.errors import MarketScannerApiError
from app.api.http import ApiHttpClient
from app.api.market_scanner.dtos.response.market_scan import MarketScan


class MarketScannerClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        identity_headers: CloudRunIdentityHeaders | None = None,
    ):
        self._http = ApiHttpClient(
            client,
            identity_headers,
            error_type=MarketScannerApiError,
        )

    async def latest_market_scan(self) -> MarketScan:
        response = await self._http.request("GET", "/v1/market-scans/latest")
        return self._http.model(response, MarketScan)

    async def close(self) -> None:
        await self._http.close()
