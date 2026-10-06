"""Real PostgreSQL graph round trip using the current Liquibase schema."""

import json

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
from test.integration import test_shared_database
from test.integration.test_shared_database import ROLES, run_liquibase
from test.report_fixtures import unsourced_analysis_payload
from test.unit.components.agents.test_regime_workflow import market_data, run_graph

shared_database = test_shared_database.shared_database


@pytest.fixture
async def local_schema(shared_database):
    owner, _, _, urls = shared_database
    await run_liquibase(urls[ROLES[2]])
    engine = create_async_engine(
        make_url(urls[ROLES[0]]).set(drivername="postgresql+asyncpg"),
    )
    try:
        await owner.execute("SET search_path TO market_scanner")
        yield owner, engine, "market_scanner"
    finally:
        await engine.dispose()


@pytest.mark.parametrize("missing", [False, True])
async def should_round_trip_the_25_asset_graph(local_schema, monkeypatch, missing):
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
