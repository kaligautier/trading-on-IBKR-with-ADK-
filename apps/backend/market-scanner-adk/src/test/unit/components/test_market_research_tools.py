"""ADK adapters use Python dates, per-scan cache and catalog identities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.adk.tools import FunctionTool
from pydantic import ValidationError

from app.components.tools import market_research as tools
from app.config.constants import (
    ASSET_WEB_RESEARCHER_INSTRUCTION,
    MARKET_SYNTHESIZER_INSTRUCTION,
)
from app.models.structured_output.unsourced_market_analysis import (
    UnsourcedMarketAnalysis,
)
from test.report_fixtures import unsourced_analysis_payload


def context():
    return SimpleNamespace(
        state={
            "analysis_date": "2026-10-07",
            "research_tool_results": {},
            "trend_market_data": {
                "assets": {
                    "sp500": {
                        "status": "success",
                        "symbol": "^GSPC",
                        "observed_on": "2026-10-05",
                    },
                    "oil": {"status": "error", "symbol": "CL=F"},
                }
            },
        }
    )


async def should_cache_global_data_within_one_scan_only(monkeypatch):
    # Arrange
    fetch = AsyncMock(
        return_value={"status": "available", "items": [{"title": "Macro"}]}
    )
    monkeypatch.setattr(tools.research_client, "get_global_news", fetch)
    first, second = context(), context()
    # Act
    a = await tools.get_global_news(first)
    b = await tools.get_global_news(first)
    await tools.get_global_news(second)
    # Assert
    assert a == b
    assert fetch.await_count == 2
    assert first.state["research_tool_results"]


async def should_use_the_instruments_observation_date_and_catalog_symbol(monkeypatch):
    # Arrange
    fetch = AsyncMock(return_value={"status": "empty", "items": []})
    monkeypatch.setattr(tools.research_client, "get_news", fetch)
    state = context()
    # Act
    await tools.get_news("sp500", state)
    unavailable = await tools.get_news("oil", state)
    # Assert
    assert fetch.await_args.args[0] == "^GSPC"
    assert fetch.await_args.args[1].isoformat() == "2026-10-05"
    assert unavailable["status"] == "unavailable"
    assert fetch.await_count == 1


async def should_bound_uncached_calls_and_allow_cached_results(monkeypatch):
    # Arrange
    state = context()
    state.state["research_tool_results"] = {str(i): {} for i in range(40)}
    fetch = AsyncMock()
    monkeypatch.setattr(tools.research_client, "get_global_news", fetch)
    # Act
    result = await tools.get_global_news(state)
    # Assert
    assert result["status"] == "unavailable"
    assert "budget" in result["reason"]
    fetch.assert_not_awaited()


def should_expose_four_valid_adk_function_declarations():
    # Arrange
    functions = [
        tools.get_news,
        tools.get_global_news,
        tools.get_macro_indicators,
        tools.get_prediction_markets,
    ]
    # Act
    declarations = [FunctionTool(function)._get_declaration() for function in functions]
    # Assert
    assert [item.name for item in declarations] == [
        function.__name__ for function in functions
    ]
    assert all("tool_context" not in str(item.parameters) for item in declarations)


def should_request_macro_mechanisms_counterevidence_and_explicit_gaps():
    # Arrange
    research, synthesis = (
        ASSET_WEB_RESEARCHER_INSTRUCTION,
        MARKET_SYNTHESIZER_INSTRUCTION,
    )
    # Act
    instructions = research + synthesis
    # Assert
    assert all(
        name in research
        for name in [
            "get_news",
            "get_global_news",
            "get_macro_indicators",
            "get_prediction_markets",
        ]
    )
    assert "transmission" in instructions and "contradict" in instructions
    assert "market-implied" in instructions
    assert "macro_overview" in synthesis and "data_gaps" in synthesis
    assert "unestablished" in synthesis and "hypothesis" in synthesis


def should_validate_a_macro_overview_without_changing_asset_calculations():
    # Arrange
    payload = unsourced_analysis_payload(["sp500"])
    payload["macro_overview"] = {
        "context": "Stocks and rates diverge.",
        "themes": [
            {
                "title": "Rate sensitivity",
                "asset_keys": ["sp500"],
                "observation": "Equities rose.",
                "development": "No usable macro series.",
                "transmission": "Lower discount rates could support growth stocks.",
                "counter_evidence": "No earnings evidence.",
                "uncertainty": "Causality remains unknown.",
                "status": "hypothesis",
            }
        ],
        "data_gaps": ["FRED unavailable"],
    }
    # Act
    result = UnsourcedMarketAnalysis.model_validate(payload)
    # Assert
    assert result.macro_overview.themes[0].status == "hypothesis"
    assert (
        result.asset_insights[0].observation
        == payload["asset_insights"][0]["observation"]
    )


@pytest.mark.parametrize("invalid", ["documented", "certain"])
def should_reject_verified_macro_causes_in_the_unsourced_contract(invalid):
    # Arrange
    payload = unsourced_analysis_payload(["sp500"])
    payload["macro_overview"] = {
        "context": "Macro",
        "themes": [
            {
                "title": "Theme",
                "asset_keys": ["sp500"],
                "observation": "Stocks rose",
                "development": "Unknown",
                "transmission": "Unknown",
                "counter_evidence": "Unknown",
                "uncertainty": "Unknown",
                "status": invalid,
            }
        ],
        "data_gaps": [],
    }
    # Act
    with pytest.raises(ValidationError) as error:
        UnsourcedMarketAnalysis.model_validate(payload)
    # Assert
    assert "status" in str(error.value)


async def should_coalesce_parallel_calls_and_keep_all_results(monkeypatch):
    # Arrange
    state = context()

    async def fetch(_as_of):
        await asyncio.sleep(0)
        return {"status": "available", "items": [{"title": "Macro"}]}

    provider = AsyncMock(side_effect=fetch)
    monkeypatch.setattr(tools.research_client, "get_global_news", provider)
    # Act
    results = await asyncio.gather(*(tools.get_global_news(state) for _ in range(3)))
    # Assert
    assert all(result == results[0] for result in results)
    assert provider.await_count == 1
    assert len(state.state["research_tool_results"]) == 1


async def should_continue_when_optional_research_is_disabled(monkeypatch):
    # Arrange
    from app.config.settings import settings

    monkeypatch.setattr(settings, "MARKET_SCANNER_RESEARCH_TOOLS_ENABLED", False)
    fetch = AsyncMock()
    monkeypatch.setattr(tools.research_client, "get_global_news", fetch)
    # Act
    result = await tools.get_global_news(context())
    # Assert
    assert result["status"] == "unavailable"
    assert "disabled" in result["reason"]
    fetch.assert_not_awaited()


def should_require_macro_content_for_new_scans_but_accept_old_public_reports():
    # Arrange
    from app.models.structured_output.market_analysis import MarketAnalysis

    payload = unsourced_analysis_payload(["sp500"])
    payload.pop("macro_overview", None)
    # Act
    old_report = MarketAnalysis.model_validate(payload)
    with pytest.raises(ValidationError) as error:
        UnsourcedMarketAnalysis.model_validate(payload)
    # Assert
    assert old_report.macro_overview is None
    assert "macro_overview" in str(error.value)


@pytest.mark.parametrize("asset_keys", [["invented"], ["sp500", "sp500"]])
def should_reject_macro_themes_outside_the_snapshot_scope(asset_keys):
    # Arrange
    from app.models.market_report import MacroOverview
    from app.models.structured_output.market_analysis import MarketAnalysis
    from app.services.market_data_trend_service import MarketDataTrendService
    from app.services.market_scan_assembler import (
        MarketScanAssembler,
        MarketScanAssemblyError,
    )
    from test.unit.components.agents.test_regime_workflow import market_data

    data = market_data()
    data.assets = {"sp500": data.assets["sp500"]}
    snapshot = MarketDataTrendService().define_trend(data)
    analysis = MarketAnalysis.model_validate(unsourced_analysis_payload(["sp500"]))
    analysis.macro_overview = MacroOverview(
        context="Macro",
        themes=[
            {
                "title": "Theme",
                "asset_keys": asset_keys,
                "observation": "Stocks rose",
                "development": "Unknown",
                "transmission": "Unknown",
                "counter_evidence": "Unknown",
                "uncertainty": "Unknown",
                "status": "unestablished",
            }
        ],
        data_gaps=[],
    )
    # Act
    with pytest.raises(MarketScanAssemblyError) as error:
        MarketScanAssembler().enrich(snapshot, analysis)
    # Assert
    assert "Macro theme" in str(error.value)


async def should_include_pending_calls_in_the_shared_budget(monkeypatch):
    # Arrange
    state = context()

    async def fetch(topic, as_of):
        await asyncio.sleep(0)
        return {"status": "empty", "items": []}

    provider = AsyncMock(side_effect=fetch)
    monkeypatch.setattr(tools.research_client, "get_prediction_markets", provider)
    # Act
    results = await asyncio.gather(
        *(tools.get_prediction_markets(str(i), state) for i in range(41))
    )
    # Assert
    assert provider.await_count == 40
    assert sum(result["status"] == "unavailable" for result in results) == 1
    assert all(
        result["status"] != "pending"
        for result in state.state["research_tool_results"].values()
    )
