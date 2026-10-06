"""Internal analysis without citations; public Report v3 keeps empty source fields."""

from typing import Literal

from app.models.market_report import (
    Family,
    Horizon,
    ReportModel,
    ReportSummary,
    ReportText,
)


class UnsourcedInterpretation(ReportModel):
    text: ReportText
    status: Literal["hypothesis", "unestablished"]


class UnsourcedAssetInsight(ReportModel):
    asset_key: str
    horizon: Horizon
    observation: ReportText
    interpretation: UnsourcedInterpretation


class UnsourcedThemeInsight(ReportModel):
    family: Family
    observation: ReportText
    interpretation: UnsourcedInterpretation


class UnsourcedMarketAnalysis(ReportSummary):
    themes: list[UnsourcedThemeInsight]
    asset_insights: list[UnsourcedAssetInsight]
