"""Domain models for market data assets and price horizons."""

import json
from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from urllib.parse import quote

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config.constants import (
    ASSET_ENTRIES,
    ASSET_SOURCE_OVERRIDES,
)

Trend = Literal["rising", "stable", "falling"]


class Asset:
    """A financial asset with its Yahoo Finance symbol and display name."""

    def __init__(self, key: str, symbol: str, name: str) -> None:
        self.key = key
        self.symbol = symbol
        self.name = name
        self.kind = "macro" if key == "us_public_debt" else "market"
        self.unit = "USD" if self.kind == "macro" else None
        self.source, self.source_url = ASSET_SOURCE_OVERRIDES.get(
            key,
            (
                "Yahoo Finance",
                f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/",
            ),
        )


class AssetCatalog:
    """Registry of tracked market assets."""

    def __init__(self, keys: tuple[str, ...] | None = None):
        selected_keys = tuple(ASSET_ENTRIES) if keys is None else keys
        if not selected_keys or set(selected_keys) - ASSET_ENTRIES.keys():
            raise ValueError("Asset selection must contain known catalog keys")
        self._assets = {
            key: Asset(
                key=key,
                symbol=symbol,
                name=name,
            )
            for key in selected_keys
            for symbol, name in (ASSET_ENTRIES[key],)
        }

    def all(self) -> dict[str, Asset]:
        return dict(self._assets)

    def get(self, key: str) -> Asset:
        return self._assets[key]


class HorizonResult:
    """Price change over a specific time horizon."""

    def __init__(self, change_percent: float, reference_price: float | str, trend: str):
        self.change_percent = change_percent
        self.reference_price = reference_price
        self.trend = trend

    def to_dict(self) -> dict:
        return {
            "change_pct": self.change_percent,
            "ref_price": self.reference_price,
            "trend": self.trend,
        }


class HorizonData(BaseModel):
    """Validated market data for one time horizon."""

    change_pct: float = Field(description="Percentage change.", allow_inf_nan=False)
    ref_price: float | Decimal = Field(
        description="Reference value at the start of the period.", allow_inf_nan=False
    )
    trend: Trend = Field(description="Direction over this period.")

    @field_validator("ref_price", mode="before")
    @classmethod
    def preserve_decimal_reference(cls, value):
        return Decimal(value) if isinstance(value, str) else value


class MarketDataAsset(BaseModel):
    """Authoritative dated observation for a market or macroeconomic asset."""

    name: str
    symbol: str
    kind: Literal["market", "macro"] = "market"
    unit: str | None = None
    trend: Trend | None = None
    status: Literal["success", "error"]
    value: float | Decimal | None = Field(default=None, allow_inf_nan=False)
    horizons: dict[str, Optional[HorizonData]] = Field(default_factory=dict)
    error: Optional[str] = None
    observed_on: date | None = None
    source: str = "Yahoo Finance"
    source_url: str | None = None
    percentile_3y: float | None = Field(default=None, ge=0, le=1)
    history_points_3y: int = Field(default=0, ge=0)

    @field_validator("value", mode="before")
    @classmethod
    def preserve_decimal_value(cls, value):
        return Decimal(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_successful_asset(self):
        if self.status == "error":
            return self
        if self.value is None:
            raise ValueError("A successful market asset requires a value")
        if not self.horizons:
            raise ValueError("A successful market asset requires horizons")
        return self

    @property
    def is_available(self) -> bool:
        return self.status == "success"


class MarketDataCollection:
    """Validated collection of authoritative market data keyed by asset ID."""

    def __init__(self, assets: dict[str, MarketDataAsset]) -> None:
        self._assets = assets

    @classmethod
    def from_json(cls, payload: str) -> "MarketDataCollection":
        raw_assets = json.loads(payload)
        if not isinstance(raw_assets, dict):
            raise ValueError("Market data must be a JSON object")
        assets = {
            key: MarketDataAsset.model_validate(raw_asset)
            for key, raw_asset in raw_assets.items()
        }
        return cls(assets)

    def available_keys(self) -> set[str]:
        return {key for key, asset in self._assets.items() if asset.is_available}

    def available_items(self) -> list[tuple[str, MarketDataAsset]]:
        return [
            (key, asset) for key, asset in self._assets.items() if asset.is_available
        ]

    def available_asset(self, key: str) -> MarketDataAsset | None:
        asset = self._assets.get(key)
        if asset is None or not asset.is_available:
            return None
        return asset

    def items(self) -> list[tuple[str, MarketDataAsset]]:
        return list(self._assets.items())
