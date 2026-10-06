"""Collect dated provider observations without calculating market indicators."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.client.market_data_client import MarketDataClient
from app.config.constants import SUCCESS
from app.models.market_assets import Asset, AssetCatalog
from app.models.step_01_external_market_data import (
    ExternalMarketAsset,
    ExternalMarketData,
    ExternalMarketObservation,
)
from app.utils.error import AppError, MarketDataCollectionError
from app.utils.wide_event import wide_event

logger = logging.getLogger(__name__)

# These identify the extracted provider field; they are not indicators.
PROVIDER_VALUE_FIELDS = {
    "Yahoo Finance": "Close",
    "U.S. Treasury": "tot_pub_debt_out_amt",
}


class MarketDataCollectionService:
    def __init__(
        self,
        asset_catalog: AssetCatalog,
        default_client: MarketDataClient,
        *,
        clients_by_symbol: dict[str, MarketDataClient] | None = None,
    ) -> None:
        self._asset_catalog = asset_catalog
        self._default_client = default_client
        self._clients_by_symbol = clients_by_symbol or {}

    def collect(self) -> ExternalMarketData:
        """Return the typed Bronze collection before any indicator calculation."""
        assets = {
            key: self.collect_asset(asset)
            for key, asset in self._asset_catalog.all().items()
        }
        available = sum(a.status == SUCCESS for a in assets.values())
        wide_event.add(
            action="market_scan.run",
            **{
                "market_data.requested_count": len(assets),
                "market_data.available_count": available,
                "market_data.unavailable_count": len(assets) - available,
            },
        )
        return ExternalMarketData(assets=assets)

    def collect_asset(self, asset: Asset) -> ExternalMarketAsset:
        metadata = {
            "name": asset.name,
            "symbol": asset.symbol,
            "kind": asset.kind,
            "unit": asset.unit,
            "source": asset.source,
            "source_url": asset.source_url,
            "value_field": PROVIDER_VALUE_FIELDS.get(asset.source),
        }
        try:
            client = self._clients_by_symbol.get(asset.symbol, self._default_client)
            if (
                isinstance(client.source_name, str)
                and client.source_name != asset.source
            ):
                raise MarketDataCollectionError(
                    f"provider_source_mismatch: catalog={asset.source}, "
                    f"client={client.source_name}"
                )
            history = client.fetch_closing_prices(asset.symbol, "10y")
            retrieved_at = datetime.now(UTC)
            if history.latest is None:
                raise MarketDataCollectionError("Provider returned no observations")
            if history.latest.observed_on > retrieved_at.date():
                raise MarketDataCollectionError(
                    "Provider returned a future observation"
                )
            return ExternalMarketAsset(
                **metadata,
                retrieved_at=retrieved_at,
                status=SUCCESS,
                observations=[
                    ExternalMarketObservation(
                        observed_on=p.observed_on,
                        value=str(p.value) if isinstance(p.value, Decimal) else p.value,
                    )
                    for p in history.prices
                ],
            )
        except Exception as error:
            # Keep collection partial: a failed asset must not discard other assets.
            app_error = (
                error
                if isinstance(error, AppError)
                else MarketDataCollectionError(
                    message=str(error),
                    details={"cause_type": type(error).__name__},
                )
            )
            wide_event.append(
                "market_data.errors",
                {"symbol": asset.symbol, "source": asset.source, **app_error.to_dict()},
            )
            logger.warning("Collection failed for %s: %s", asset.symbol, app_error)
            return ExternalMarketAsset(
                **metadata,
                retrieved_at=datetime.now(UTC),
                status="error",
                error=app_error.message,
            )
