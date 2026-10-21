"""Composition root for the native Momentum ADK workflow."""

from google.adk import Workflow

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.components.agents.momentum.workflow.nodes import MomentumNodeFactory
from app.components.callbacks.statistics import MomentumStatistics
from app.domain.contracts import AnalysisRequest, WorkflowResult


class MomentumWorkflowFactory:
    """Build the typed, resumable ADK workflow graph."""

    def __init__(
        self,
        quick_model: str,
        deep_model: str,
        statistics: MomentumStatistics | None = None,
    ) -> None:
        self._quick_model = quick_model
        self._deep_model = deep_model
        self._statistics = statistics or MomentumStatistics()

    def create(self) -> Workflow:
        catalog = MomentumAgentCatalog(
            self._quick_model,
            self._deep_model,
            self._statistics,
        )
        nodes = MomentumNodeFactory(
            catalog,
            self._statistics,
            self._quick_model,
        )
        selected_analysts = nodes.selected_analysts()
        research = nodes.research()
        trader = nodes.trader()
        risk = nodes.risk()
        portfolio = nodes.portfolio()
        result = nodes.result()
        return Workflow(
            name="momentum_analysis",
            input_schema=AnalysisRequest,
            output_schema=WorkflowResult,
            edges=[
                (
                    "START",
                    selected_analysts,
                    research,
                    trader,
                    risk,
                    portfolio,
                    result,
                )
            ],
        )
