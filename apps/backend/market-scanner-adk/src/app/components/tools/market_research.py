"""ADK tool adapters: scope and analysis dates come from Python, not the model."""

import asyncio
from datetime import date

from google.adk.tools import ToolContext

from app.client.market_research_client import MarketResearchClient
from app.config.settings import settings

research_client = MarketResearchClient(fred_api_key=settings.FRED_API_KEY)
# Tasks live only while I/O is running; JSON session state contains data only.
_inflight: dict[tuple[int, str], asyncio.Task] = {}


async def _call(name, arguments, as_of, tool_context):
    state = tool_context.state
    key = "|".join((name, as_of.isoformat(), *arguments))
    cache = state.get("research_tool_results", {})
    flight_key = (id(cache), key)
    if flight_key in _inflight:
        result = await _inflight[flight_key]
        state["research_tool_results"] = cache
        return result
    if key in cache:
        return cache[key]
    if len(cache) >= 40:
        return {
            "status": "unavailable",
            "reason": "Per-scan research call budget exhausted",
            "items": [],
        }
    # Reserve the slot before yielding: parallel calls cannot exceed the budget.
    cache[key] = {"status": "pending", "items": []}
    state["research_tool_results"] = cache

    async def fetch():
        if not settings.MARKET_SCANNER_RESEARCH_TOOLS_ENABLED:
            return {
                "status": "unavailable",
                "reason": "Optional research tools disabled",
                "items": [],
            }
        return await getattr(research_client, name)(*arguments, as_of)

    task = asyncio.create_task(fetch())
    _inflight[flight_key] = task
    try:
        result = await task
        cache[key] = result
        state["research_tool_results"] = cache
        return result
    finally:
        _inflight.pop(flight_key, None)


def _date(tool_context):
    return date.fromisoformat(tool_context.state["analysis_date"])


async def get_news(asset_key: str, tool_context: ToolContext) -> dict:
    """Get catalog-tagged Yahoo news over the week ending at its observation date."""
    asset = tool_context.state["trend_market_data"]["assets"].get(asset_key, {})
    observed = asset.get("observed_on")
    if asset.get("status") != "success" or not observed:
        return {
            "status": "unavailable",
            "reason": "Asset unavailable or observation date unknown",
            "items": [],
        }
    as_of = min(date.fromisoformat(observed), _date(tool_context))
    return await _call("get_news", (asset["symbol"],), as_of, tool_context)


async def get_global_news(tool_context: ToolContext) -> dict:
    """Get a dated global macro news sample; empty is not absence of market news."""
    return await _call("get_global_news", (), _date(tool_context), tool_context)


async def get_macro_indicators(indicator: str, tool_context: ToolContext) -> dict:
    """Get point-in-time FRED observations and units.

    Indicators: cpi, core_pce, unemployment, payrolls, gdp, fedfunds,
    treasury_2y, treasury_10y, yield_curve, ecb_deposit_rate, eurozone_hicp.
    """
    return await _call(
        "get_macro_indicators", (indicator,), _date(tool_context), tool_context
    )


async def get_prediction_markets(topic: str, tool_context: ToolContext) -> dict:
    """Get live Polymarket odds, volume and resolution dates.

    Withheld for historical scans; market-implied probabilities are not facts.
    """
    return await _call(
        "get_prediction_markets", (topic[:120],), _date(tool_context), tool_context
    )
