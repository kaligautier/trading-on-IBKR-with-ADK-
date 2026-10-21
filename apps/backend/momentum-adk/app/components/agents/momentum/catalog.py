"""ADK agent catalog for all Momentum roles."""

from __future__ import annotations

from typing import ClassVar

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.workflow import RetryConfig

from app.components.agents.momentum.prompts import MomentumPromptCatalog
from app.components.callbacks.statistics import MomentumStatistics
from app.components.tools.market_data import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_global_news,
    get_income_statement,
    get_indicators,
    get_insider_transactions,
    get_latest_market_scan,
    get_news,
    get_stock_data,
)
from app.config.llm import LiteLLMGatewayModel
from app.domain.analysis import (
    AggressiveArgument,
    BearArgument,
    BullArgument,
    ConservativeArgument,
    FundamentalsAnalysis,
    MarketAnalysis,
    NeutralArgument,
    NewsAnalysis,
    PortfolioDecision,
    ResearchPlan,
    SentimentAnalysis,
    TraderProposal,
)
from app.domain.state import ReflectionText


class MomentumAgentCatalog:
    """Construct and expose the twelve stable Momentum agent roles."""

    ANALYST_SCHEMAS: ClassVar[dict[str, type]] = {
        "market": MarketAnalysis,
        "social": SentimentAnalysis,
        "news": NewsAnalysis,
        "fundamentals": FundamentalsAnalysis,
    }
    ANALYST_TOOLS: ClassVar[dict[str, list]] = {
        "market": [get_stock_data, get_indicators, get_latest_market_scan],
        "social": [get_news],
        "news": [get_news, get_global_news, get_insider_transactions],
        "fundamentals": [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ],
    }
    ROLE_SCHEMAS: ClassVar[dict[str, type]] = {
        "bull": BullArgument,
        "bear": BearArgument,
        "research_manager": ResearchPlan,
        "trader": TraderProposal,
        "aggressive": AggressiveArgument,
        "conservative": ConservativeArgument,
        "neutral": NeutralArgument,
        "portfolio_manager": PortfolioDecision,
    }
    DEEP_ROLES: ClassVar[frozenset[str]] = frozenset(
        {"research_manager", "portfolio_manager"}
    )
    RETRY_CONFIG: ClassVar[RetryConfig] = RetryConfig(
        max_attempts=3,
        initial_delay=1,
        max_delay=8,
        backoff_factor=2,
        jitter=0.2,
    )

    def __init__(
        self,
        quick_model: LiteLLMGatewayModel,
        deep_model: LiteLLMGatewayModel,
        statistics: MomentumStatistics | None = None,
    ) -> None:
        if not all(
            isinstance(m, LiteLLMGatewayModel) for m in (quick_model, deep_model)
        ):
            raise ValueError("Momentum agents require gateway model objects")
        self._quick_model = quick_model
        self._deep_model = deep_model
        self._statistics = statistics or MomentumStatistics()
        self._prompts = MomentumPromptCatalog()
        self._agents = self._build_agents()
        self._agents["reflection"] = self._structured_agent(
            "reflection", ReflectionText
        )
        self._analyst_workflows = self._build_analyst_workflows()

    @property
    def role_names(self) -> set[str]:
        return set(self.ANALYST_SCHEMAS) | set(self.ROLE_SCHEMAS)

    def agent(self, role: str) -> LlmAgent:
        return self._agents[role]

    def analyst_workflow(self, role: str) -> Workflow:
        return self._analyst_workflows[role]

    def _build_agents(self) -> dict[str, LlmAgent]:
        agents: dict[str, LlmAgent] = {}
        for role, schema in self.ANALYST_SCHEMAS.items():
            agents[f"{role}_collector"] = self._collector(role)
            agents[role] = self._structured_agent(role, schema, formatter=True)
        for role, schema in self.ROLE_SCHEMAS.items():
            agents[role] = self._structured_agent(role, schema)
        return agents

    def _collector(self, role: str) -> LlmAgent:
        return LlmAgent(
            name=f"{role}_collector",
            model=self._quick_model,
            mode="single_turn",
            include_contents="none",
            instruction=self._prompts.analyst(role),
            tools=self.ANALYST_TOOLS[role],
            retry_config=self.RETRY_CONFIG,
            before_model_callback=self._statistics.before_model,
            after_model_callback=self._statistics.after_model,
            before_tool_callback=self._statistics.before_tool,
        )

    def _structured_agent(
        self,
        role: str,
        schema: type,
        formatter: bool = False,
    ) -> LlmAgent:
        instruction = (
            self._prompts.formatter(role) if formatter else self._prompts.role(role)
        )
        model = self._deep_model if role in self.DEEP_ROLES else self._quick_model
        return LlmAgent(
            name=role,
            model=model,
            mode="single_turn",
            include_contents="none",
            instruction=instruction,
            output_schema=schema,
            retry_config=self.RETRY_CONFIG,
            before_model_callback=self._statistics.before_model,
            after_model_callback=self._statistics.after_model,
            before_tool_callback=self._statistics.before_tool,
        )

    def _build_analyst_workflows(self) -> dict[str, Workflow]:
        return {
            role: Workflow(
                name=f"{role}_analysis",
                output_schema=schema,
                edges=[
                    ("START", self._agents[f"{role}_collector"]),
                    (self._agents[f"{role}_collector"], self._agents[role]),
                ],
            )
            for role, schema in self.ANALYST_SCHEMAS.items()
        }
