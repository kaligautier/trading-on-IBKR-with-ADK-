"""MCP-level contract tests for the public tool allowlist."""

from datetime import date
from uuid import UUID

import pytest
from fastmcp import Client

from app.api.market_scanner.dtos.response.market_scan import MarketScan
from app.api.momentum.dtos.response.analyses import (
    AnalysisSummary,
    ReaderPage,
)
from app.api.momentum.dtos.response.suggestions import Suggestion
from app.core_components.resources.public_resources import (
    MomentumPublicResources,
)
from app.core_components.tools.public_tools import MomentumPublicTools
from app.server import PUBLIC_TOOL_NAMES, MomentumPublicMcpServer

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
        return ReaderPage(items=[summary()], next_page_token="")

    async def latest_analyses(self, ticker, ratings, page):
        return ReaderPage(items=[summary()], next_page_token="")

    async def get_analysis(self, analysis_id):
        raise AssertionError("not used")

    async def get_recommendations(self, ratings, page):
        return ReaderPage(items=[summary()], next_page_token="")

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


async def test_suggestion_schema_hides_internal_actor_identifiers(mcp_server) -> None:
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    by_name = {registered_tool.name: registered_tool for registered_tool in tools}
    suggestion_schema = by_name["momentum_suggest_ticker"].output_schema
    exposed_fields = set(suggestion_schema["properties"])
    assert "suggested_by" not in exposed_fields
    assert "reviewed_by" not in exposed_fields


async def test_list_tool_returns_structured_validated_data(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("momentum_list_analyses", {"ticker": "aapl"})

    assert result.data.items[0].ticker == "AAPL"


async def test_suggestion_normalizes_symbol_and_passes_pseudonym(
    mcp_server,
    gateway: StubGateway,
) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "momentum_suggest_ticker",
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
