"""Collect, compute trends, research and assemble qualitative market analysis."""

from datetime import UTC, datetime

from google.adk import Context, Event, Workflow
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.adk.workflow import node
from google.genai import types

from app.client.treasury_client import TreasuryClient
from app.client.yahoo_finance_client import YahooFinanceClient
from app.components.callbacks.after_agent import record_agent_end
from app.components.callbacks.before_agent import record_agent_start
from app.components.callbacks.tool_callbacks import record_tool_end, record_tool_start
from app.components.tools.market_research import (
    get_global_news,
    get_macro_indicators,
    get_news,
    get_prediction_markets,
)
from app.config.constants import (
    ASSEMBLE_MARKET_DATA,
    ASSET_WEB_RESEARCHER_INSTRUCTION,
    ENRICH_MARKET_DATA,
    GET_MARKET_DATA,
    MARKET_RESEARCH_CRITIC_INSTRUCTION,
    MARKET_RESEARCH_CRITIC_NAME,
    MARKET_SCANNER,
    MARKET_SCANNER_AGENT_MODE,
    MARKET_SYNTHESIZER_INSTRUCTION,
    MARKET_SYNTHESIZER_NAME,
    MARKET_WEB_RESEARCHER_NAME,
    PERSIST_MARKET_SCAN,
    STATE_ANALYSED_MARKET_DATA,
    STATE_MARKET_ANALYSIS,
    STATE_MARKET_DATA,
    STATE_RESEARCH_CAPTURE_COUNT,
    STATE_RESEARCH_CLAIMS,
    STATE_RESEARCH_CRITIQUE,
    STATE_RESEARCH_EVIDENCE_AUDIT,
    STATE_RESEARCH_SOURCES,
    STATE_SESSION_ID,
    STATE_TREND_MARKET_DATA,
    STATE_WEB_ANALYSIS,
)
from app.config.settings import settings
from app.models.market_assets import AssetCatalog
from app.models.step_02_trend_market_data import TrendMarketData
from app.models.step_03_analysed_market_data import (
    AnalysedMarketData,
)
from app.models.step_04_market_data import MarketData
from app.models.structured_output.market_analysis import MarketAnalysis
from app.models.structured_output.research_critique import ResearchCritique
from app.models.structured_output.unsourced_market_analysis import (
    UnsourcedMarketAnalysis,
)
from app.services.market_data_collection_service import MarketDataCollectionService
from app.services.market_data_trend_service import MarketDataTrendService
from app.services.market_scan_assembler import MarketScanAssembler
from app.services.market_scan_persistence import MarketScanPersistence
from app.utils.error import MarketDataUnavailableError

market_scan_assembler = MarketScanAssembler()

market_data_collection_service = MarketDataCollectionService(
    AssetCatalog(settings.MARKET_SCANNER_ASSET_KEYS),
    default_client=YahooFinanceClient(),
    clients_by_symbol={
        "US_PUBLIC_DEBT": TreasuryClient(),
    },
)

market_data_trend_service = MarketDataTrendService()

gemini_model = Gemini(
    model=settings.MODEL,
    client_kwargs={
        "enterprise": settings.GOOGLE_GENAI_USE_VERTEXAI,
        "project": settings.GOOGLE_CLOUD_PROJECT,
        "location": settings.GOOGLE_CLOUD_LOCATION,
    },
)


@node(name=GET_MARKET_DATA, rerun_on_resume=True)
def get_market_data(context: Context) -> Event:
    """Collect and compute locally; expose only indicators and provenance."""
    context.event_author = GET_MARKET_DATA
    external_market_data = market_data_collection_service.collect()
    market_data_horizon = market_data_trend_service.define_trend(external_market_data)
    if not market_data_horizon.to_collection().available_keys():
        raise MarketDataUnavailableError()
    payload = market_data_horizon.model_dump(mode="json")
    event = Event(
        output=payload,
        state={
            STATE_TREND_MARKET_DATA: payload,
            "analysis_date": datetime.now(UTC).date().isoformat(),
            "research_tool_results": {},
            STATE_RESEARCH_CRITIQUE: {},
            # Clear legacy citation state when reusing an existing session.
            STATE_RESEARCH_SOURCES: [],
            STATE_RESEARCH_CLAIMS: [],
            STATE_RESEARCH_CAPTURE_COUNT: 0,
            STATE_RESEARCH_EVIDENCE_AUDIT: {},
        },
    )
    return event


researcher = LlmAgent(
    name=MARKET_WEB_RESEARCHER_NAME,
    model=gemini_model,
    mode=MARKET_SCANNER_AGENT_MODE,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel(settings.RESEARCHER_THINKING_LEVEL),
            include_thoughts=True,
        ),
    ),
    static_instruction=None,
    instruction=ASSET_WEB_RESEARCHER_INSTRUCTION,
    output_schema=None,
    tools=[
        google_search,
        get_news,
        get_global_news,
        get_macro_indicators,
        get_prediction_markets,
    ],
    output_key=STATE_WEB_ANALYSIS,
    include_contents="none",
    before_agent_callback=record_agent_start,
    after_agent_callback=record_agent_end,
    before_tool_callback=record_tool_start,
    after_tool_callback=record_tool_end,
)


critic = LlmAgent(
    name=MARKET_RESEARCH_CRITIC_NAME,
    model=gemini_model,
    mode=MARKET_SCANNER_AGENT_MODE,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel(settings.CRITIC_THINKING_LEVEL),
            include_thoughts=True,
        ),
    ),
    instruction=MARKET_RESEARCH_CRITIC_INSTRUCTION,
    output_schema=ResearchCritique,
    output_key=STATE_RESEARCH_CRITIQUE,
    include_contents="none",
    before_agent_callback=record_agent_start,
    after_agent_callback=record_agent_end,
)


synthesizer = LlmAgent(
    name=MARKET_SYNTHESIZER_NAME,
    model=gemini_model,
    mode=MARKET_SCANNER_AGENT_MODE,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel(settings.SYNTHESIZER_THINKING_LEVEL),
            include_thoughts=True,
        ),
    ),
    instruction=MARKET_SYNTHESIZER_INSTRUCTION,
    output_schema=UnsourcedMarketAnalysis,
    output_key=STATE_MARKET_ANALYSIS,
    include_contents="none",
    before_agent_callback=record_agent_start,
    after_agent_callback=record_agent_end,
)


@node(name=ENRICH_MARKET_DATA, rerun_on_resume=True)
def enrich_market_data(context: Context, node_input: UnsourcedMarketAnalysis) -> Event:
    """Keep validated analysis and asset identities in their own snapshot."""
    analysis = MarketAnalysis.model_validate(node_input.model_dump(mode="json"))
    analysed = market_scan_assembler.enrich(
        TrendMarketData.model_validate(context.state[STATE_TREND_MARKET_DATA]),
        analysis,
        [],
    )
    payload = analysed.model_dump(mode="json")
    event = Event(
        output=payload,
        state={
            STATE_ANALYSED_MARKET_DATA: payload,
        },
    )
    return event


@node(name=ASSEMBLE_MARKET_DATA, rerun_on_resume=True)
def assemble_market_data(
    context: Context, analysed_market_data: AnalysedMarketData
) -> Event:
    market_data = market_scan_assembler.assemble(
        TrendMarketData.model_validate(context.state[STATE_TREND_MARKET_DATA]),
        analysed_market_data,
    )
    payload = market_data.model_dump(mode="json")
    event = Event(output=payload, state={STATE_MARKET_DATA: payload})
    return event


@node(name=PERSIST_MARKET_SCAN, rerun_on_resume=True)
async def persist_market_scan(context: Context, market_data: MarketData) -> Event:
    session_id = str(context.state.get(STATE_SESSION_ID, "adk-market-scanner"))
    await MarketScanPersistence().save(market_data.market_regime, session_id)
    # Return only the final result, preserving explicit nulls during ADK transport.
    return Event(output=market_data.model_dump(mode="json"))


root_agent = Workflow(
    name=MARKET_SCANNER,
    edges=[
        ("START", get_market_data),
        (get_market_data, researcher),
        (researcher, critic),
        (critic, synthesizer),
        (synthesizer, enrich_market_data),
        (enrich_market_data, assemble_market_data),
        (assemble_market_data, persist_market_scan),
    ],
)
