"""MCP-level contract tests for the public tool allowlist."""

import json
from datetime import date
from uuid import UUID

import pytest
from fastmcp import Client

from momentum_public_mcp.api.market_scanner.dtos.response.market_scan import MarketScan
from momentum_public_mcp.api.momentum.dtos.response.analyses import AnalysisSummary
from momentum_public_mcp.api.momentum.dtos.response.suggestions import Suggestion
from momentum_public_mcp.domain import AnalysisSummaries
from momentum_public_mcp.mcp.resources.public_resources import (
    LATEST_MARKET_SCAN_URI,
    MomentumPublicResources,
)
from momentum_public_mcp.mcp.tools.public_tools import MomentumPublicTools
from momentum_public_mcp.server import PUBLIC_TOOL_NAMES, MomentumPublicMcpServer

ANALYSIS_ID = UUID("11111111-1111-1111-1111-111111111111")
SUGGESTION_ID = UUID("22222222-2222-2222-2222-222222222222")


class StaticFingerprint:
    def current(self) -> str:
        return "caller-fingerprint"


class StubGateway:
    def __init__(self) -> None:
        self.suggested_symbol = None
        self.caller_fingerprint = None

    async def list_analyses(self, ticker, page):
        return AnalysisSummaries((summary(),))

    async def latest_analyses(self, ticker, ratings):
        return AnalysisSummaries((summary(),))

    async def get_analysis(self, analysis_id):
        raise AssertionError("not used")

    async def get_recommendations(self, ratings, limit):
        return AnalysisSummaries((summary(),))

    async def latest_market_scan(self):
        return market_scan()

    async def suggest_ticker(self, symbol, reason, caller_fingerprint):
        self.suggested_symbol = symbol.value
        self.caller_fingerprint = caller_fingerprint
        return suggestion()

    async def get_suggestion_status(self, suggestion_id):
        return suggestion()


@pytest.fixture
def gateway() -> StubGateway:
    return StubGateway()


@pytest.fixture
def mcp_server(gateway: StubGateway):
    tools = MomentumPublicTools(gateway, StaticFingerprint())
    return MomentumPublicMcpServer(
        tools, resources=MomentumPublicResources(gateway)
    ).server


async def test_exposes_only_the_explicit_public_allowlist(mcp_server) -> None:
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    names = {registered_tool.name for registered_tool in tools}
    forbidden_fragments = {"admin", "approve", "reject", "launch", "job", "task"}
    assert names == PUBLIC_TOOL_NAMES
    exposed_forbidden_name = any(
        fragment in name for name in names for fragment in forbidden_fragments
    )
    assert not exposed_forbidden_name


async def test_read_tools_have_read_only_annotations(mcp_server) -> None:
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    by_name = {registered_tool.name: registered_tool for registered_tool in tools}
    read_names = PUBLIC_TOOL_NAMES - {"suggest_ticker"}
    assert all(by_name[name].annotations.read_only_hint is True for name in read_names)
    assert by_name["suggest_ticker"].annotations.destructive_hint is False


async def test_suggestion_schema_hides_internal_actor_identifiers(mcp_server) -> None:
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    by_name = {registered_tool.name: registered_tool for registered_tool in tools}
    suggestion_schema = by_name["suggest_ticker"].output_schema
    exposed_fields = set(suggestion_schema["properties"])
    assert "suggested_by" not in exposed_fields
    assert "reviewed_by" not in exposed_fields


async def test_list_tool_returns_structured_validated_data(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("list_analyses", {"ticker": "aapl"})

    assert result.data[0].ticker == "AAPL"


async def test_market_scan_resource_returns_current_scanner_data(mcp_server) -> None:
    async with Client(mcp_server) as client:
        contents = await client.read_resource(LATEST_MARKET_SCAN_URI)

    assert contents[0].mime_type == "application/json"
    assert json.loads(contents[0].text)["report"]["regime"] == "risk-on"


async def test_suggestion_normalizes_symbol_and_passes_pseudonym(
    mcp_server,
    gateway: StubGateway,
) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "suggest_ticker",
            {"symbol": " msft ", "reason": "Strong fundamentals"},
        )

    assert result.data.status == "pending"
    assert gateway.suggested_symbol == "MSFT"
    assert gateway.caller_fingerprint == "caller-fingerprint"


def summary() -> AnalysisSummary:
    return AnalysisSummary(
        id=ANALYSIS_ID,
        ticker="AAPL",
        analysis_date=date(2026, 8, 1),
        created_at=None,
        llm_provider="google",
        next_analysis_date=None,
    )


def suggestion() -> Suggestion:
    return Suggestion(
        id=SUGGESTION_ID,
        symbol="MSFT",
        reason="Strong fundamentals",
        status="pending",
        suggested_by="pseudonym",
        source="mcp",
        created_at="2026-08-02T00:00:00Z",
        reviewed_at=None,
        reviewed_by=None,
        review_reason=None,
    )


def market_scan() -> MarketScan:
    return MarketScan(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        scan_date=date(2026, 8, 6),
        report={"schema_version": 3, "regime": "risk-on", "assets": []},
        created_at="2026-08-06T10:00:00Z",
    )
