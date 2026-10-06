"""Exercise the real ADK graph with external boundaries stubbed."""

import copy
import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from google.adk import Workflow
from google.adk.models import LlmResponse
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.application import create_app
from app.components.agents.market_scanner import agent as scanner
from app.config.settings import settings
from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)
from app.models.market_assets import AssetCatalog
from app.models.step_01_external_market_data import ExternalMarketData
from app.models.step_02_trend_market_data import TrendMarketData
from app.models.step_03_analysed_market_data import AnalysedMarketData
from app.models.step_04_market_data import MarketData
from app.services.market_data_collection_service import MarketDataCollectionService
from app.utils.error import MarketDataUnavailableError
from test.report_fixtures import unsourced_analysis_payload


def market_data():
    today = date.today()
    client = Mock()
    client.fetch_closing_prices.return_value = ClosingPriceHistory(
        tuple(
            ClosingPrice(today - timedelta(days=offset), 4800.0)
            for offset in range(1, 401)
        )
        + (ClosingPrice(today, 5000.0),)
    )
    return MarketDataCollectionService(AssetCatalog(), client).collect()


def conclusion(data):
    return unsourced_analysis_payload(
        key for key, asset in data.assets.items() if asset.status == "success"
    )


async def run_graph(agent=None):
    async with InMemoryRunner(
        agent=scanner.root_agent if agent is None else agent, app_name="market_scanner"
    ) as runner:
        session = await runner.session_service.create_session(
            app_name="market_scanner",
            user_id="test-user",
            state={
                "session_id": "test-scan",
                "research_sources": [{"id": "STALE"}],
                "research_claims": [{"claim_id": "STALE"}],
                "research_capture_count": 99,
                "research_evidence_audit": {"stale": True},
            },
        )
        events = [
            event
            async for event in runner.run_async(
                user_id="test-user",
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text="Scan")]),
            )
        ]
        final = await runner.session_service.get_session(
            app_name="market_scanner", user_id="test-user", session_id=session.id
        )
        return events, final


@pytest.mark.parametrize("unavailable_key", [None, "vix"])
async def should_keep_stage_outputs_separate_and_return_only_the_final_result(
    monkeypatch, unavailable_key
):
    data = market_data()
    if unavailable_key:
        data.assets[unavailable_key] = data.assets[unavailable_key].model_copy(
            update={
                "status": "error",
                "observations": [],
                "error": "source unavailable",
            }
        )
    before = copy.deepcopy(data)
    steps, saved = [], []

    def collect():
        steps.append("collection")
        return data

    async def respond(_self, llm_request, stream=False):
        assert _self.model == settings.MODEL
        instruction = str(llm_request.config.system_instruction)
        assert "5000" in instruction and "^GSPC" in instruction
        assert '"observations"' not in instruction
        assert "retrieved_at" in instruction
        assert "value_field" in instruction
        assert "capitalization-weighted" in instruction
        assert "Only analyse assets with status success" in instruction
        is_research = "research" not in steps
        steps.append("research" if is_research else "conclusion")
        if is_research:
            output = "Dated research on current market risks."
        else:
            assert "Dated research on current market risks." in instruction
            thinking = llm_request.config.thinking_config
            assert thinking.thinking_level == settings.SYNTHESIZER_THINKING_LEVEL
            output = json.dumps(conclusion(data))
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    async def save(_self, regime, session_id):
        steps.append("persistence")
        saved.append((regime, session_id))
        return regime

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", collect)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    events, final = await run_graph()
    assert events
    assert events[0].author == "get_market_data"
    assert events[0].node_info.path.endswith("/get_market_data@1")
    assert events[1].author == "market_web_researcher"
    assert steps == ["collection", "research", "conclusion", "persistence"]
    assert data == before
    assert "external_market_data" not in final.state
    assert '"observations"' not in json.dumps(final.state)
    for event in events:
        assert '"observations"' not in event.model_dump_json()
    assert all(
        "horizons" not in asset for asset in data.model_dump()["assets"].values()
    )
    assert "trend_market_data_for_llm" not in final.state
    assert len(events) == 6
    assert (
        final.state["trend_market_data"]["assets"]["sp500"]["horizons"]["1m"][
            "change_pct"
        ]
        == 4.17
    )
    result, session_id = saved[0]
    assert session_id == "test-scan"
    assert result.regime == conclusion(data)["regime"]
    assert "regime_assessment" not in final.state
    assert "regime_probabilities" not in result.model_dump()
    assert final.state["market_data"]["market_regime"] == result.model_dump(mode="json")
    complete = MarketData.model_validate(final.state["market_data"])
    assert set(complete.model_dump()) == {"market_regime"}
    trends = TrendMarketData.model_validate(final.state["trend_market_data"])
    analysis = AnalysedMarketData.model_validate(final.state["analysed_market_data"])
    assert analysis.summary == conclusion(data)["summary"]
    assert final.state["web_analysis"] == "Dated research on current market risks."
    assert analysis.regime == "cautious"
    for key, trend in trends.assets.items():
        analysed = analysis.assets[key]
        assert analysed.model_dump(exclude={"insight"}) == {
            "name": trend.name,
            "symbol": trend.symbol,
        }
        if trend.status == "success":
            assert analysed.insight.observation == "One-day observation."
            assembled = next(
                asset
                for asset in complete.market_regime.assets
                if asset.symbol == trend.symbol
            )
            assert assembled.value == trend.value
            assert assembled.horizons == trend.horizons
            assert assembled.trend == trend.trend
            assert assembled.observation == analysed.insight.observation
            assert assembled.interpretation == analysed.insight.interpretation
        else:
            assert analysed.insight is None
            assert complete.market_regime.data_quality[key].status == "unavailable"
            assert all(
                asset.symbol != trend.symbol for asset in complete.market_regime.assets
            )
    assert [set(event.actions.state_delta) for event in events] == [
        {
            "trend_market_data",
            "analysis_date",
            "research_tool_results",
            "research_sources",
            "research_claims",
            "research_capture_count",
            "research_evidence_audit",
        },
        {"web_analysis"},
        {"market_analysis"},
        {"analysed_market_data"},
        {"market_data"},
        set(),
    ]
    assert events[0].output == final.state["trend_market_data"]
    assert all(
        set(insight) == {"asset_key", "horizon", "observation", "interpretation"}
        for insight in final.state["market_analysis"]["asset_insights"]
    )
    assert events[3].output == final.state["analysed_market_data"]
    assert (
        events[4].output
        == events[5].output
        == {"market_regime": result.model_dump(mode="json")}
    )
    result_keys = list(events[-1].output["market_regime"])
    assert (
        result_keys.index("summary")
        < result_keys.index("themes")
        < result_keys.index("assets")
    )
    assert "recommendation" not in result_keys
    assert final.state["research_sources"] == []
    assert final.state["research_claims"] == []
    assert final.state["research_capture_count"] == 0
    assert events[0].actions.state_delta["research_evidence_audit"] == {}
    assert final.state["research_evidence_audit"] == {}
    assert "market_scanner@1" in events[-1].node_info.output_for


async def should_run_steps_01_and_02_without_preparing_llm_input(monkeypatch):
    data = market_data()
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    generate = AsyncMock()
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    workflow = Workflow(
        name="market_scanner",
        edges=[
            ("START", scanner.get_market_data),
        ],
    )

    _, final = await run_graph(workflow)

    generate.assert_not_called()
    assert "trend_market_data_for_llm" not in final.state
    assert "observations" not in final.state["trend_market_data"]["assets"]["sp500"]
    assert final.state["trend_market_data"]["assets"]["sp500"]["horizons"]


@pytest.mark.parametrize(
    "data",
    [
        ExternalMarketData(assets={}),
        ExternalMarketData(
            assets={
                "sp500": market_data()
                .assets["sp500"]
                .model_copy(
                    update={
                        "status": "error",
                        "observations": [],
                        "error": "unavailable",
                    }
                )
            }
        ),
    ],
)
async def should_stop_before_llm_and_persistence_without_available_data(
    monkeypatch, data
):
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    generate, save = AsyncMock(), AsyncMock()
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    with pytest.raises(MarketDataUnavailableError):
        await run_graph()
    generate.assert_not_called()
    save.assert_not_called()


async def should_reject_documented_output_without_sources_over_sse(monkeypatch):
    data, calls = market_data(), []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        payload = conclusion(data)
        payload["asset_insights"][0]["interpretation"].update(status="documented")
        output = "Research" if len(calls) == 1 else json.dumps(payload)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    # The HTTP agent loader creates its own scanner module and service instance.
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda _self: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    monkeypatch.setattr(settings, "MARKET_SCANNER_TOKEN", "")
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        session = await client.post(
            "/apps/market_scanner/users/evidence-test/sessions", json={"state": {}}
        )
        assert session.status_code == 200
        response = await client.post(
            "/run_sse",
            json={
                "appName": "market_scanner",
                "userId": "evidence-test",
                "sessionId": session.json()["id"],
                "streaming": False,
                "newMessage": {"role": "user", "parts": [{"text": "Scan"}]},
            },
        )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert response.status_code == 200
    assert any("documented" in str(event.get("error", "")) for event in events)
    assert not any(event.get("output", {}).get("market_regime") for event in events)
    assert not any(
        event.get("actions", {}).get("stateDelta", {}).get("research_evidence_audit")
        for event in events
    )
    save.assert_not_called()


async def should_not_persist_when_the_agent_invents_an_asset(monkeypatch):
    data, calls = market_data(), []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        payload = conclusion(data)
        payload["asset_insights"][0]["asset_key"] = "invented"
        output = "Research" if len(calls) == 1 else json.dumps(payload)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    with pytest.raises(ValueError, match="invented"):
        await run_graph()
    save.assert_not_called()


async def should_analyse_one_available_asset_without_a_weighted_coverage_gate(
    monkeypatch,
):
    data = market_data()
    data.assets = {"sp500": data.assets["sp500"]}
    calls = []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        output = "Research" if len(calls) == 1 else json.dumps(conclusion(data))
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)

    _, final = await run_graph()

    assert len(calls) == 2
    save.assert_awaited_once()
    result = final.state["market_data"]
    assert result["market_regime"]["regime"] == "cautious"
    assert [asset["symbol"] for asset in result["market_regime"]["assets"]] == ["^GSPC"]
    assert "regime_assessment" not in result
    assert "regime_probabilities" not in result["market_regime"]


async def should_ignore_provider_citations_and_return_an_unsourced_report(monkeypatch):
    data = market_data()
    data.assets = {"sp500": data.assets["sp500"]}
    calls = []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        if len(calls) == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text="Factual fixture statement.")]
                ),
                grounding_metadata=types.GroundingMetadata(
                    grounding_chunks=[
                        {
                            "web": {
                                "uri": "https://example.org/fact",
                                "title": "Bulletin",
                            }
                        }
                    ],
                    grounding_supports=[
                        {
                            "segment": {"text": "Factual fixture statement."},
                            "grounding_chunk_indices": [0],
                        }
                    ],
                ),
            )
        else:
            instruction = str(llm_request.config.system_instruction)
            assert "https://example.org/fact" not in instruction
            assert "STALE" not in instruction
            payload = conclusion(data)
            payload["asset_insights"][0]["interpretation"].update(
                status="hypothesis",
                text="Factual fixture statement.",
            )
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(payload))]
                )
            )

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    events, final = await run_graph()
    report = final.state["market_data"]["market_regime"]
    assert scanner.researcher.after_model_callback is None
    assert report["sources"] == []
    assert report["assets"][0]["interpretation"]["source_ids"] == []
    assert final.state["research_claims"] == []
    assert final.state["research_evidence_audit"] == {}
    assert not any("research_claims" in e.actions.state_delta for e in events[1:])
    assert "claim_ids" not in json.dumps(report)
    save.assert_awaited_once()


@pytest.mark.parametrize(
    "invalid", [{"status": "documented"}, {"source_ids": ["S1"]}, {"claim_ids": ["C1"]}]
)
async def should_reject_citations_and_documented_status_before_persistence(
    monkeypatch, invalid
):
    data, calls = market_data(), []

    async def respond(_self, llm_request, stream=False):
        calls.append(llm_request)
        payload = conclusion(data)
        payload["asset_insights"][0]["interpretation"].update(**invalid)
        output = (
            "Research without grounding" if len(calls) == 1 else json.dumps(payload)
        )
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    with pytest.raises(ValueError):
        await run_graph()
    save.assert_not_called()
