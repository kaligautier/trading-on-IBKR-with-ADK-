"""Persist the typed scanner output in the shared normalized schema."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import settings
from app.models.market_regime import MarketRegime
from app.services.database import get_engine
from app.utils.wide_event import wide_event


class MarketScanPersistence:
    """Write every scanner run in the normalized PostgreSQL schema."""

    async def save(self, regime: MarketRegime, session_id: str) -> MarketRegime:
        wide_event.add(**{"scan.session_id": session_id})
        if not settings.DATABASE_URL:
            wide_event.add(**{"persistence.status": "not_configured"})
            return regime
        try:
            await self._persist(regime, session_id)
        except Exception:
            wide_event.add(**{"persistence.status": "error"})
            raise
        wide_event.add(**{"persistence.status": "committed"})
        return regime

    async def _persist(self, regime: MarketRegime, session_id: str) -> None:
        sessions = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sessions.begin() as session:
            await self._save_scan(session, regime, session_id)

    async def _save_scan(
        self, session: AsyncSession, regime: MarketRegime, session_id: str
    ) -> None:
        scan_id = uuid4()
        await session.execute(
            text(f"""
                INSERT INTO "{settings.DATABASE_SCHEMA}".market_scans
                (id, scan_date, session_id, regime, summary, recommendation,
                 data_quality, report, created_at)
                VALUES (:id, :scan_date, :session_id, :regime, :summary,
                        NULL, CAST(:data_quality AS JSONB),
                        CAST(:report AS JSONB), :created_at)
            """),
            {
                "id": scan_id,
                "scan_date": date.today(),
                "session_id": session_id,
                "regime": regime.regime,
                "summary": regime.summary,
                "report": regime.model_dump_json(),
                "created_at": datetime.now(UTC),
                **{
                    key: json.dumps(value) if value is not None else None
                    for key, value in regime.model_dump(
                        mode="json", include={"data_quality"}
                    ).items()
                },
            },
        )
        for asset in regime.assets:
            await self._save_asset(session, scan_id, asset, regime.sources)

    async def _save_asset(self, session: AsyncSession, scan_id, asset, sources) -> None:
        asset_id = uuid4()
        await session.execute(
            text(f"""
                INSERT INTO "{settings.DATABASE_SCHEMA}".market_scan_assets
                (id, scan_id, name, symbol, kind, unit, value, trend, analysis, context)
                VALUES (:id, :scan_id, :name, :symbol, :kind, :unit, :value, :trend,
                        :analysis, :context)
            """),
            {
                "id": asset_id,
                "scan_id": scan_id,
                "name": asset.name,
                "symbol": asset.symbol,
                "kind": asset.kind,
                "unit": asset.unit,
                "value": Decimal(str(asset.value)),
                "trend": asset.trend,
                "analysis": f"{asset.observation} {asset.interpretation.text}",
                "context": " ; ".join(
                    f"[{source.title}]({source.url})"
                    for source in sources
                    if source.id in asset.interpretation.source_ids
                ),
            },
        )
        for horizon, data in asset.horizons.items():
            if data is None:
                continue
            await session.execute(
                text(f"""
                    INSERT INTO "{settings.DATABASE_SCHEMA}".market_scan_horizons
                    (id, asset_id, horizon, change_pct, ref_price, trend)
                    VALUES (:id, :asset_id, :horizon, :change_pct, :ref_price, :trend)
                """),
                {
                    "id": uuid4(),
                    "asset_id": asset_id,
                    "horizon": horizon,
                    "change_pct": data.change_pct,
                    "ref_price": Decimal(str(data.ref_price)),
                    "trend": data.trend,
                },
            )
