"""Validate report coverage and citations, then join authoritative observations."""

from datetime import date

from app.models.market_assets import MarketDataAsset, MarketDataCollection
from app.models.market_regime import AssetAnalysis, MarketRegime
from app.models.market_report import (
    ASSET_FAMILIES,
    ReportScope,
    ResearchSource,
    ThemeAnalysis,
)
from app.models.scan_metadata import DataQuality
from app.models.step_02_trend_market_data import TrendMarketData
from app.models.step_03_analysed_market_data import (
    AnalysedMarketAsset,
    AnalysedMarketData,
)
from app.models.step_04_market_data import MarketData
from app.models.structured_output.market_analysis import MarketAnalysis
from app.services.data_freshness import is_fresh
from app.utils.wide_event import wide_event


class MarketScanAssemblyError(ValueError):
    """The interpretation cannot be joined to this run's observations/evidence."""


class MarketScanAssembler:
    def enrich(
        self,
        trend_market_data: TrendMarketData,
        analysis: MarketAnalysis,
        sources: list[ResearchSource] | None = None,
    ) -> AnalysedMarketData:
        sources = sources or []
        self._validate(trend_market_data.to_collection(), analysis, sources)
        insights = {insight.asset_key: insight for insight in analysis.asset_insights}
        return AnalysedMarketData(
            **analysis.model_dump(exclude={"asset_insights"}),
            assets={
                key: AnalysedMarketAsset(
                    name=asset.name, symbol=asset.symbol, insight=insights.get(key)
                )
                for key, asset in trend_market_data.assets.items()
            },
            sources=sources,
        )

    def assemble(
        self,
        trend_market_data: TrendMarketData,
        analysed_market_data: AnalysedMarketData,
    ) -> MarketData:
        analysis = MarketAnalysis(
            **analysed_market_data.model_dump(exclude={"assets", "sources"}),
            asset_insights=[
                asset.insight
                for asset in analysed_market_data.assets.values()
                if asset.insight is not None
            ],
        )
        return MarketData(
            market_regime=self.assemble_regime(
                trend_market_data.to_collection(),
                analysis,
                analysed_market_data.sources,
            )
        )

    @staticmethod
    def _validate(
        data: MarketDataCollection,
        analysis: MarketAnalysis,
        sources: list[ResearchSource],
    ) -> None:
        available = data.available_keys()
        if analysis.macro_overview:
            for theme in analysis.macro_overview.themes:
                if (
                    len(theme.asset_keys) != len(set(theme.asset_keys))
                    or not set(theme.asset_keys) <= available
                ):
                    raise MarketScanAssemblyError(
                        "Macro theme references duplicate or unavailable assets"
                    )
        keys = [insight.asset_key for insight in analysis.asset_insights]
        if len(keys) != len(set(keys)):
            raise MarketScanAssemblyError("Duplicate asset insights")
        if set(keys) != available:
            raise MarketScanAssemblyError(
                f"Asset coverage mismatch: missing={sorted(available - set(keys))}, "
                f"unknown/unavailable={sorted(set(keys) - available)}"
            )
        families = [theme.family for theme in analysis.themes]
        expected = {
            key
            for key, members in ASSET_FAMILIES.items()
            if available.intersection(members)
        }
        if len(families) != len(set(families)) or set(families) != expected:
            raise MarketScanAssemblyError("Theme coverage mismatch")
        for insight in analysis.asset_insights:
            asset = data.available_asset(insight.asset_key)
            if (
                insight.horizon != "level"
                and asset.horizons.get(insight.horizon) is None
            ):
                raise MarketScanAssemblyError(
                    f"Unavailable horizon for {insight.asset_key}"
                )
        if analysis.horizon != "level" and not any(
            asset.horizons.get(analysis.horizon) is not None
            for _, asset in data.available_items()
        ):
            raise MarketScanAssemblyError("Unavailable report horizon")
        registry = {source.id: source for source in sources}
        if len(registry) != len(sources):
            raise MarketScanAssemblyError("Duplicate source IDs")
        for item in [*analysis.themes, *analysis.asset_insights]:
            interpretation = item.interpretation
            for source_id in interpretation.source_ids:
                if source_id not in registry:
                    raise MarketScanAssemblyError(
                        f"Unknown research source: {source_id}"
                    )
                if (
                    interpretation.status == "documented"
                    and not registry[source_id].supported_claims
                ):
                    raise MarketScanAssemblyError(
                        f"Source without grounding support: {source_id}"
                    )

    def assemble_regime(
        self,
        market_data: MarketDataCollection,
        interpretation: MarketAnalysis,
        sources: list[ResearchSource] | None = None,
    ) -> MarketRegime:
        sources = sources or []
        self._validate(market_data, interpretation, sources)
        insights = {
            insight.asset_key: insight for insight in interpretation.asset_insights
        }
        quality = {key: self._quality(asset) for key, asset in market_data.items()}
        source_ids = {
            source_id
            for item in [*interpretation.themes, *interpretation.asset_insights]
            for source_id in item.interpretation.source_ids
        }
        available = market_data.available_keys()
        regime = MarketRegime(
            **interpretation.model_dump(exclude={"asset_insights", "themes"}),
            scope=ReportScope(
                requested=len(quality),
                available=len(available),
                observation_dates=sorted(
                    {
                        asset.observed_on
                        for _, asset in market_data.available_items()
                        if asset.observed_on is not None
                    }
                ),
                unavailable=[
                    key
                    for key, value in quality.items()
                    if value.status == "unavailable"
                ],
                stale=[
                    key for key, value in quality.items() if value.status == "stale"
                ],
            ),
            themes=[
                ThemeAnalysis(
                    **theme.model_dump(),
                    asset_keys=[
                        key for key in ASSET_FAMILIES[theme.family] if key in available
                    ],
                )
                for theme in interpretation.themes
            ],
            assets=[
                AssetAnalysis(
                    **insights[key].model_dump(),
                    **asset.model_dump(
                        exclude={"status", "error", "source", "source_url"}
                    ),
                )
                for key, asset in market_data.available_items()
            ],
            sources=[source for source in sources if source.id in source_ids],
            data_quality=quality,
        )
        wide_event.add(
            **{
                "scan.regime": regime.regime,
                "scan.asset_count": len(regime.assets),
                "scan.source_count": len(regime.sources),
                "scan.schema_version": regime.schema_version,
            }
        )
        return regime

    @staticmethod
    def _quality(asset: MarketDataAsset) -> DataQuality:
        fresh = is_fresh(asset.observed_on, date.today())
        status = (
            "unavailable"
            if not asset.is_available
            else "available"
            if fresh
            else "stale"
        )
        return DataQuality(
            name=asset.name,
            symbol=asset.symbol,
            source=asset.source,
            source_url=asset.source_url,
            observed_on=asset.observed_on,
            status=status,
            reason=asset.error
            if not asset.is_available
            else None
            if fresh
            else "stale_observation",
        )
