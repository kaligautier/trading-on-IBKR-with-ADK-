from google.adk.models import LlmResponse
from google.genai import types

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.components.callbacks.statistics import MomentumStatistics
from app.config.llm import create_model
from app.config.settings import Settings


def test_statistics_collect_model_tool_and_token_usage():
    statistics = MomentumStatistics()
    response = LlmResponse(
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=120,
            candidates_token_count=45,
        )
    )

    assert statistics.before_model(None, None) is None
    assert statistics.before_tool(None, {}, None) is None
    assert statistics.after_model(None, response) is None

    snapshot = statistics.snapshot()
    assert snapshot.llm_calls == 1
    assert snapshot.tool_calls == 1
    assert snapshot.tokens_in == 120
    assert snapshot.tokens_out == 45


def test_statistics_callbacks_accept_adk_keyword_contracts():
    statistics = MomentumStatistics()
    response = LlmResponse()

    assert statistics.before_model(callback_context=None, llm_request=None) is None
    assert statistics.before_tool(tool=None, args={}, tool_context=None) is None
    assert statistics.after_model(callback_context=None, llm_response=response) is None


def test_statistics_reset_starts_a_fresh_execution():
    statistics = MomentumStatistics()
    statistics.before_model(None, None)
    statistics.before_tool(None, {}, None)

    statistics.reset()

    assert statistics.snapshot().model_dump() == {
        "agents_total": 0,
        "agents_completed": 0,
        "llm_calls": 0,
        "tool_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "reports_total": 0,
        "reports_completed": 0,
        "duration_seconds": 0.0,
    }


def test_catalog_attaches_statistics_to_all_model_agents():
    statistics = MomentumStatistics()
    catalog = MomentumAgentCatalog(
        quick_model=create_model(
            Settings(
                LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test"
            ),
            "quick",
        ),
        deep_model=create_model(
            Settings(
                LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test"
            ),
            "deep",
        ),
        statistics=statistics,
    )

    collector = catalog.agent("market_collector")
    manager = catalog.agent("portfolio_manager")

    assert collector.before_model_callback == statistics.before_model
    assert collector.after_model_callback == statistics.after_model
    assert collector.before_tool_callback == statistics.before_tool
    assert manager.before_model_callback == statistics.before_model
    assert manager.after_model_callback == statistics.after_model
