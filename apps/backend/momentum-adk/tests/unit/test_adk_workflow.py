from google.adk import Workflow
from google.adk.agents import LlmAgent

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.components.agents.momentum.workflow import MomentumWorkflowFactory
from app.components.callbacks.statistics import MomentumStatistics
from app.config.llm import create_model
from app.config.rate_limit import ModelRequestGate
from app.config.settings import Settings
from app.domain.analysis import MarketAnalysis, PortfolioDecision
from app.domain.contracts import AnalysisRequest, WorkflowResult

GATE = ModelRequestGate()


def model(name):
    return create_model(
        Settings(LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test"),
        name,
        GATE,
    )


def test_agent_catalog_exposes_all_twelve_existing_roles():
    catalog = MomentumAgentCatalog(
        quick_model=model("quick"),
        deep_model=model("deep"),
    )

    assert catalog.role_names == {
        "market",
        "social",
        "news",
        "fundamentals",
        "bull",
        "bear",
        "research_manager",
        "trader",
        "aggressive",
        "conservative",
        "neutral",
        "portfolio_manager",
    }


def test_tool_using_analyst_separates_collection_from_structuring():
    catalog = MomentumAgentCatalog(
        quick_model=model("quick"),
        deep_model=model("deep"),
    )

    market_workflow = catalog.analyst_workflow("market")
    collector = catalog.agent("market_collector")
    formatter = catalog.agent("market")

    assert isinstance(market_workflow, Workflow)
    assert isinstance(collector, LlmAgent)
    assert collector.tools
    assert collector.output_schema is None
    assert formatter.tools == []
    assert formatter.output_schema is MarketAnalysis


def test_portfolio_manager_uses_deep_model_and_structured_output():
    catalog = MomentumAgentCatalog(
        quick_model=model("quick"),
        deep_model=model("deep"),
    )

    portfolio_manager = catalog.agent("portfolio_manager")

    assert portfolio_manager.model.model == "deep"
    assert portfolio_manager.output_schema is PortfolioDecision
    assert portfolio_manager.retry_config.max_attempts == 3


def test_root_workflow_has_typed_boundaries():
    root_agent = MomentumWorkflowFactory(
        quick_model=model("quick"),
        deep_model=model("deep"),
    ).create()

    assert isinstance(root_agent, Workflow)
    assert root_agent.input_schema is AnalysisRequest
    assert root_agent.output_schema is WorkflowResult


def test_workflow_uses_injected_statistics_collector():
    statistics = MomentumStatistics()

    root_agent = MomentumWorkflowFactory(
        quick_model=model("quick"),
        deep_model=model("deep"),
        statistics=statistics,
    ).create()

    assert root_agent.input_schema is AnalysisRequest


def test_follow_up_date_has_a_seven_day_minimum():
    from datetime import date
    from types import SimpleNamespace

    import pytest

    from app.components.agents.momentum.workflow.results import WorkflowResultBuilder
    from app.domain.state import NextAnalysisRecommendation

    reports = SimpleNamespace(request=SimpleNamespace(analysis_date=date(2026, 10, 21)))
    outcome = SimpleNamespace(
        risk=SimpleNamespace(
            trader=SimpleNamespace(research=SimpleNamespace(reports=reports))
        )
    )
    for day in (20, 21, 27):
        with pytest.raises(ValueError, match="seven days"):
            WorkflowResultBuilder(MomentumStatistics()).build(
                outcome,
                NextAnalysisRecommendation(
                    analysis_date=date(2026, 10, day), description="Review"
                ),
            )
