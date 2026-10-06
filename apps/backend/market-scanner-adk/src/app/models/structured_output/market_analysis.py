"""Qualitative output only; Python supplies prices, scope and source URLs."""

from app.models.market_report import AssetInsight, ReportSummary, ThemeInsight

__all__ = ["AssetInsight", "MarketAnalysis"]


class MarketAnalysis(ReportSummary):
    themes: list[ThemeInsight]
    asset_insights: list[AssetInsight]
