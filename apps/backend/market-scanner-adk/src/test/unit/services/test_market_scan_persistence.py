"""Tests for Market Scanner PostgreSQL persistence."""

import json
from decimal import Decimal

import pytest

from app.config.settings import settings
from app.models.market_regime import (
    AssetAnalysis,
    MarketRegime,
)
from app.models.structured_output.market_analysis import MarketAnalysis
from app.services import market_scan_persistence
from app.services.database import async_database_url
from app.services.market_scan_assembler import MarketScanAssembler
from app.services.market_scan_persistence import (
    MarketScanPersistence,
)
from app.utils.wide_event import wide_event
from test.report_fixtures import analysis_payload, explanation
from test.unit.services.test_market_scan_assembler import data_for


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement, parameters: dict) -> None:
        self.calls.append((str(statement), parameters))


async def should_store_metadata_as_json_without_losing_debt_cents():
    regime = _regime()
    regime.assets = [
        AssetAnalysis(
            asset_key="us_public_debt",
            horizon="1m",
            name="US federal debt",
            symbol="US_PUBLIC_DEBT",
            kind="macro",
            unit="USD",
            value="40047726949770.15",
            trend="rising",
            observation="Macroeconomic context.",
            interpretation=explanation(),
            horizons={
                "1m": {
                    "ref_price": "39000000000000.05",
                    "change_pct": 2.69,
                    "trend": "rising",
                }
            },
        )
    ]
    regime.data_quality = {}
    session = RecordingSession()
    await MarketScanPersistence()._save_scan(session, regime, "metadata-test")
    sql, parameters = session.calls[0]
    assert "CAST(:data_quality AS JSONB)" in sql
    assert json.loads(parameters["data_quality"]) == {}
    assert "regime_details" not in sql
    assert "macro_indicators" not in sql
    asset_sql, asset_params = session.calls[1]
    assert f'INSERT INTO "{settings.DATABASE_SCHEMA}".market_scan_assets' in asset_sql
    assert asset_params["value"] == Decimal("40047726949770.15")
    assert asset_params["kind"] == "macro"
    assert session.calls[2][1]["ref_price"] == Decimal("39000000000000.05")
    assert regime.model_dump(mode="json")["assets"][0]["value"] == "40047726949770.15"


def should_convert_aiven_sslmode_for_asyncpg():
    database_url = (
        "postgresql://user:password@db.example:5432/defaultdb?sslmode=require"
    )

    result = async_database_url(database_url)

    assert (
        result
        == "postgresql+asyncpg://user:password@db.example:5432/defaultdb?ssl=require"
    )


@pytest.mark.parametrize("trend", ["rising", None])
async def should_forward_ytd_and_missing_overall_trends_to_persistence(trend):
    regime = _regime()
    regime.assets = [
        AssetAnalysis(
            asset_key="sp500",
            horizon="ytd" if trend else "level",
            name="S&P 500",
            symbol="^GSPC",
            value=110,
            trend=trend,
            observation="Observation.",
            interpretation=explanation(),
            horizons={
                "ytd": {
                    "ref_price": 100,
                    "change_pct": 10,
                    "trend": trend,
                }
                if trend
                else None,
            },
        )
    ]
    session = RecordingSession()
    await MarketScanPersistence()._save_scan(session, regime, "ytd-test")
    assert session.calls[1][1]["trend"] == trend
    if trend:
        assert session.calls[2][1]["horizon"] == "ytd"
        assert session.calls[2][1]["trend"] == trend
    else:
        assert len(session.calls) == 2


def should_preserve_an_asyncpg_url_without_sslmode():
    database_url = "postgresql+asyncpg://user:password@db.example/defaultdb"

    result = async_database_url(database_url)

    assert result == database_url


def _regime() -> MarketRegime:
    return MarketScanAssembler().assemble_regime(
        data_for(), MarketAnalysis.model_validate(analysis_payload(["sp500"]))
    )


async def should_record_when_persistence_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    scope = wide_event.start({"event": "http.request"})
    try:
        result = await MarketScanPersistence().save(_regime(), "session-42")
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)

    assert result == _regime()
    assert event["scan.session_id"] == "session-42"
    assert event["persistence.status"] == "not_configured"


async def should_record_a_safe_persistence_failure(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://database")

    def fail_to_create_engine():
        raise RuntimeError("password=must-not-be-logged")

    monkeypatch.setattr(
        market_scan_persistence,
        "get_engine",
        fail_to_create_engine,
    )
    scope = wide_event.start({"event": "http.request"})
    try:
        with pytest.raises(RuntimeError):
            await MarketScanPersistence().save(_regime(), "session-42")
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)

    assert event["persistence.status"] == "error"
    assert "password" not in str(event)


async def should_persist_the_scan_without_probabilities_or_weighted_scores():
    session = RecordingSession()
    regime = _regime()

    await MarketScanPersistence()._save_scan(session, regime, "session-1")

    statement, parameters = session.calls[0]
    assert "probability" not in statement
    assert "regime_details" not in statement
    assert not any("probability" in key for key in parameters)
    assert parameters["regime"] == "cautious"
    assert "regime_confidence" not in parameters
    assert "regime_confidence" not in statement


async def should_store_the_complete_versioned_report_without_an_allocation():
    session = RecordingSession()
    report = _regime()
    await MarketScanPersistence()._save_scan(session, report, "v3")
    sql, parameters = session.calls[0]
    assert "CAST(:report AS JSONB)" in sql
    assert "NULL, CAST(:data_quality" in sql
    assert "recommendation" not in parameters
    assert MarketRegime.model_validate_json(parameters["report"]) == report
