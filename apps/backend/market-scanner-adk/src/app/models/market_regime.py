"""Version 3: summary, family findings, asset details and attributable evidence."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.models.market_assets import HorizonData, Trend
from app.models.market_report import (
    AssetInsight,
    ReportScope,
    ReportSummary,
    ResearchSource,
    ThemeAnalysis,
)
from app.models.scan_metadata import DataQuality


class AssetAnalysis(AssetInsight):
    name: str
    symbol: str
    kind: Literal["market", "macro"] = "market"
    unit: str | None = None
    observed_on: date | None = None
    value: float | Decimal = Field(allow_inf_nan=False)
    horizons: dict[str, HorizonData | None]
    trend: Trend | None = None
    percentile_3y: float | None = Field(default=None, ge=0, le=1)
    history_points_3y: int = 0

    @field_validator("value", mode="before")
    @classmethod
    def preserve_decimal_value(cls, value):
        return Decimal(value) if isinstance(value, str) else value


class MarketRegime(ReportSummary):
    schema_version: Literal[3] = 3
    scope: ReportScope
    themes: list[ThemeAnalysis]
    assets: list[AssetAnalysis]
    sources: list[ResearchSource]
    data_quality: dict[str, DataQuality]
