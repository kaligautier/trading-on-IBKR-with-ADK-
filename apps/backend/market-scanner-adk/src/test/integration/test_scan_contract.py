"""Real PostgreSQL migration and graph round trip in an isolated local schema."""

import json
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from google.adk.models import LlmResponse
from google.adk.models.google_llm import Gemini
from google.genai import types
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.components.agents.market_scanner import agent as scanner
from app.config.settings import settings
from app.models.market_regime import MarketRegime
from app.services.market_scan_persistence import MarketScanPersistence
from test.report_fixtures import unsourced_analysis_payload
from test.unit.components.agents.test_regime_workflow import market_data, run_graph

ROOT = Path(__file__).resolve().parents[3]
BASELINE = """
CREATE TABLE market_scans (
    id UUID PRIMARY KEY, scan_date DATE NOT NULL, session_id TEXT NOT NULL,
    regime TEXT NOT NULL, summary TEXT NOT NULL, recommendation TEXT NOT NULL,
    data_quality JSONB, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE market_scan_assets (
    id UUID PRIMARY KEY, scan_id UUID REFERENCES market_scans(id), name TEXT NOT NULL,
    symbol TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'market', unit TEXT,
    value NUMERIC NOT NULL, trend TEXT NOT NULL,
    analysis TEXT NOT NULL, context TEXT NOT NULL
);
CREATE TABLE market_scan_horizons (
    id UUID PRIMARY KEY, asset_id UUID REFERENCES market_scan_assets(id),
    horizon TEXT NOT NULL, change_pct DOUBLE PRECISION NOT NULL,
    ref_price NUMERIC NOT NULL, trend TEXT NOT NULL
);
INSERT INTO market_scans VALUES (
    '00000000-0000-0000-0000-000000000001', '2020-01-02', 'legacy', 'cautious',
    'Preserved history', 'moderate', NULL, '2020-01-02'
);
"""


@pytest.fixture
async def local_schema():
    database_url = os.getenv("MARKET_REPORT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set MARKET_REPORT_TEST_DATABASE_URL to an isolated local PostgreSQL"
        )
    address = make_url(database_url)
    if address.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("Report integration tests require a local PostgreSQL host")
    connection = await asyncpg.connect(
        address.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    schema = f"report_test_{uuid4().hex}"
    engine = create_async_engine(
        address.set(drivername="postgresql+asyncpg"),
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'SET search_path TO "{schema}"')
        await connection.execute(BASELINE)
        migration = (ROOT / "migrations/001_market_report_v2.sql").read_text()
        await connection.execute(migration)
        await connection.execute(migration)  # Reapplying must preserve historical rows.
        yield connection, engine, schema
    finally:
        await engine.dispose()
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


@pytest.mark.parametrize("missing", [False, True])
async def should_round_trip_the_25_asset_graph_and_preserve_legacy(
    local_schema, monkeypatch, missing
):
    connection, engine, schema = local_schema
    data = market_data()
    data.assets["vixeq"].observations = data.assets["vixeq"].observations[-1:]
    data.assets["us_public_debt"].kind = "macro"
    data.assets["us_public_debt"].unit = "USD"
    for observation in data.assets["us_public_debt"].observations:
        observation.value = "40047726949770.15"
    if missing:
        data.assets["vix"].status = "error"
        data.assets["vix"].error = "Fixture unavailable"
        data.assets["vix"].observations = []
    calls = []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        if len(calls) == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text="Fictional research.")]
                ),
                grounding_metadata=types.GroundingMetadata(
                    grounding_chunks=[
                        {
                            "web": {
                                "uri": "https://example.org/research",
                                "title": "Fixture",
                            }
                        }
                    ],
                    grounding_supports=[
                        {
                            "segment": {"text": "Fictional research."},
                            "grounding_chunk_indices": [0],
                        }
                    ],
                ),
            )
        else:
            payload = unsourced_analysis_payload(
                key for key, asset in data.assets.items() if asset.status == "success"
            )
            for item in payload["asset_insights"]:
                if item["asset_key"] == "vixeq":
                    item["horizon"] = "level"
            payload["asset_insights"][0]["interpretation"].update(
                status="hypothesis", text="Fictional research."
            )
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(payload))]
                )
            )

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://local-test")
    monkeypatch.setattr(
        "app.services.market_scan_persistence.get_engine", lambda: engine
    )
    monkeypatch.setattr(settings, "DATABASE_SCHEMA", schema)
    _, final = await run_graph()
    expected = MarketRegime.model_validate(final.state["market_data"]["market_regime"])
    row = await connection.fetchrow(
        "SELECT report, recommendation FROM market_scans WHERE session_id='test-scan'"
    )
    persisted = MarketRegime.model_validate_json(row["report"])
    assert persisted == expected
    assert persisted.schema_version == 3
    assert persisted.regime == "cautious"
    assert all(
        item.interpretation.status in {"documented", "hypothesis", "unestablished"}
        for item in persisted.assets
    )
    stored_directions = await connection.fetch(
        "SELECT DISTINCT trend FROM market_scan_horizons"
    )
    assert {row["trend"] for row in stored_directions} <= {
        "rising",
        "falling",
        "stable",
    }
    assert len(calls) == 2
    assert len(persisted.assets) == (24 if missing else 25)
    assert row["recommendation"] is None
    assert persisted.sources == []
    assert all(asset.interpretation.source_ids == [] for asset in persisted.assets)
    assert persisted.scope.unavailable == (["vix"] if missing else [])
    assert (
        await connection.fetchval(
            "SELECT trend FROM market_scan_assets WHERE symbol='^VIXEQ'"
        )
        is None
    )
    debt = next(
        asset for asset in persisted.assets if asset.asset_key == "us_public_debt"
    )
    assert str(debt.value) == "40047726949770.15"
    assert (
        str(
            await connection.fetchval(
                "SELECT value FROM market_scan_assets WHERE symbol='US_PUBLIC_DEBT'"
            )
        )
        == "40047726949770.15"
    )
    legacy = await connection.fetchrow(
        "SELECT summary, recommendation, report FROM market_scans "
        "WHERE session_id='legacy'"
    )
    assert tuple(legacy) == ("Preserved history", "moderate", None)


async def should_roll_back_the_whole_report_when_an_asset_write_fails(
    local_schema, monkeypatch
):
    connection, engine, schema = local_schema
    from test.unit.services.test_market_scan_persistence import _regime

    report = _regime()
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://local-test")
    monkeypatch.setattr(
        "app.services.market_scan_persistence.get_engine", lambda: engine
    )
    monkeypatch.setattr(settings, "DATABASE_SCHEMA", schema)
    await connection.execute(
        "ALTER TABLE market_scan_assets ADD CONSTRAINT test_failure CHECK (value < 0)"
    )
    with pytest.raises(Exception, match="test_failure"):
        await MarketScanPersistence().save(report, "must-rollback")
    assert (
        await connection.fetchval(
            "SELECT count(*) FROM market_scans WHERE session_id='must-rollback'"
        )
        == 0
    )
