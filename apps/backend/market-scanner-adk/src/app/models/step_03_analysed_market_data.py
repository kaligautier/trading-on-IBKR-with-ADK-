"""Step 03: validated conclusions, identities and provider source references."""

from app.models.market_report import (
    AssetInsight,
    ReportModel,
    ReportSummary,
    ResearchSource,
    ThemeInsight,
)


class AnalysedMarketAsset(ReportModel):
    name: str
    symbol: str
    insight: AssetInsight | None = None


class AnalysedMarketData(ReportSummary):
    themes: list[ThemeInsight]
    assets: dict[str, AnalysedMarketAsset]
    sources: list[ResearchSource]
