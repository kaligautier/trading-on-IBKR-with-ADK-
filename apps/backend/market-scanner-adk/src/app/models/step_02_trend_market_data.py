"""Step 02: computed indicators and provenance, without raw observations."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat

from app.models.market_assets import (
    HorizonData,
    MarketDataAsset,
    MarketDataCollection,
    Trend,
)


class TrendMarketAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    symbol: str
    kind: Literal["market", "macro"]
    unit: str | None
    source: str
    source_url: str
    value_field: str | None
    retrieved_at: AwareDatetime
    status: Literal["success", "error"]
    error: str | None = None
    value: FiniteFloat | str | None = None
    observed_on: date | None = None
    horizons: dict[str, HorizonData | None] = Field(default_factory=dict)
    trend: Trend | None = Field(
        default=None, description="YTD direction; null when YTD is unavailable."
    )
    percentile_3y: float | None = Field(default=None, ge=0, le=1)
    history_points_3y: int = Field(default=0, ge=0)


class TrendMarketData(BaseModel):
    """Deterministic indicators without collection history."""

    model_config = ConfigDict(extra="forbid")

    assets: dict[str, TrendMarketAsset]

    def to_collection(self) -> MarketDataCollection:
        """Adapt the typed trends to the deterministic regime model."""
        return MarketDataCollection(
            {
                key: MarketDataAsset.model_validate(asset.model_dump())
                for key, asset in self.assets.items()
            }
        )
