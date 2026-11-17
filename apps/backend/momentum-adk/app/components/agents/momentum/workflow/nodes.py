"""ADK node definitions for the deterministic Momentum graph."""

from google.adk import Context
from google.adk.agents import LlmAgent
from google.adk.workflow import node

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.components.agents.momentum.prompts import MomentumPromptCatalog
from app.components.agents.momentum.workflow.analysts import AnalystCoordinator
from app.components.agents.momentum.workflow.debates import InvestmentDebate, RiskDebate
from app.components.agents.momentum.workflow.results import WorkflowResultBuilder
from app.components.callbacks.statistics import MomentumStatistics
from app.domain.analysis import PortfolioDecision, TraderProposal
from app.domain.contracts import AnalysisRequest, WorkflowResult
from app.domain.state import (
    AnalystReports,
    NextAnalysisRecommendation,
    PortfolioOutcome,
    ResearchOutcome,
    RiskOutcome,
    TraderOutcome,
)


class MomentumNodeFactory:
    """Create the six typed nodes used by the root workflow."""

    def __init__(
        self,
        catalog: MomentumAgentCatalog,
        statistics: MomentumStatistics,
        quick_model: str,
    ) -> None:
        self._catalog = catalog
        self._statistics = statistics
        self._quick_model = quick_model

    def selected_analysts(self):
        coordinator = AnalystCoordinator(self._catalog)
        statistics = self._statistics

        @node(name="selected_analysts", rerun_on_resume=True)
        async def run_selected_analysts(
            context: Context,
            node_input: AnalysisRequest,
        ) -> AnalystReports:
            statistics.reset()
            return await coordinator.execute(context, node_input)

        return run_selected_analysts

    def research(self):
        catalog = self._catalog

        @node(name="investment_debate", rerun_on_resume=True)
        async def run_research(
            context: Context,
            node_input: AnalystReports,
        ) -> ResearchOutcome:
            return await InvestmentDebate(node_input).execute(context, catalog)

        return run_research

    def trader(self):
        catalog = self._catalog

        @node(name="trader_proposal", rerun_on_resume=True)
        async def run_trader(
            context: Context,
            node_input: ResearchOutcome,
        ) -> TraderOutcome:
            output = await context.run_node(
                catalog.agent("trader"),
                node_input.model_dump(mode="json"),
                run_id="trader",
            )
            return TraderOutcome(
                research=node_input,
                proposal=TraderProposal.model_validate(output),
            )

        return run_trader

    def risk(self):
        catalog = self._catalog

        @node(name="risk_debate", rerun_on_resume=True)
        async def run_risk(
            context: Context,
            node_input: TraderOutcome,
        ) -> RiskOutcome:
            return await RiskDebate(node_input).execute(context, catalog)

        return run_risk

    def portfolio(self):
        catalog = self._catalog

        @node(name="portfolio_decision", rerun_on_resume=True)
        async def run_portfolio(
            context: Context,
            node_input: RiskOutcome,
        ) -> PortfolioOutcome:
            output = await context.run_node(
                catalog.agent("portfolio_manager"),
                node_input.model_dump(mode="json"),
                run_id="portfolio-manager",
            )
            return PortfolioOutcome(
                risk=node_input,
                decision=PortfolioDecision.model_validate(output),
            )

        return run_portfolio

    def result(self):
        next_analysis = self._next_analysis_agent()
        result_builder = WorkflowResultBuilder(self._statistics)

        @node(name="workflow_result", rerun_on_resume=True)
        async def build_result(
            context: Context,
            node_input: PortfolioOutcome,
        ) -> WorkflowResult:
            recommendation = await context.run_node(
                next_analysis,
                node_input.model_dump(mode="json"),
                run_id="next-analysis",
            )
            next_run = NextAnalysisRecommendation.model_validate(recommendation)
            return result_builder.build(node_input, next_run)

        return build_result

    def _next_analysis_agent(self) -> LlmAgent:
        return LlmAgent(
            name="next_analysis",
            model=self._quick_model,
            mode="single_turn",
            include_contents="none",
            instruction=MomentumPromptCatalog().role("next_analysis"),
            output_schema=NextAnalysisRecommendation,
            retry_config=self._catalog.RETRY_CONFIG,
            before_model_callback=self._statistics.before_model,
            after_model_callback=self._statistics.after_model,
            before_tool_callback=self._statistics.before_tool,
        )
