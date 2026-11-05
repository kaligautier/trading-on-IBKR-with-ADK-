"""Construct the Market Scanner client with its own Cloud Run audience."""

from app.api.auth import backend_headers, create_identity_headers
from app.api.config import create_http_client
from app.api.market_scanner.client.market_scanner_client import (
    MarketScannerClient,
)
from app.api.market_scanner.config.settings import (
    MarketScannerApiSettings,
)


def create_market_scanner_client(
    settings: MarketScannerApiSettings, *, use_iam: bool
) -> MarketScannerClient:
    client = create_http_client(
        settings.MARKET_SCANNER_API_URL,
        headers=backend_headers(settings.MARKET_SCANNER_API_TOKEN, use_iam=use_iam),
    )
    return MarketScannerClient(
        client=client,
        identity_headers=create_identity_headers(
            client, settings.MARKET_SCANNER_API_URL, use_iam=use_iam
        ),
    )
