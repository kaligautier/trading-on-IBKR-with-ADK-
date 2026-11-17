"""Bounded investment and risk debates for Momentum."""

from google.adk import Context

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.domain.analysis import BearArgument, BullArgument, ResearchPlan
from app.domain.state import (
    AnalystReports,
    ResearchOutcome,
    RiskOutcome,
    TraderOutcome,
)


class InvestmentDebate:
    """Run alternating bull and bear arguments for a bounded number of rounds."""

    def __init__(self, reports: AnalystReports) -> None:
        self._reports = reports
        self._bulls: list[BullArgument] = []
        self._bears: list[BearArgument] = []

    async def execute(
        self,
        context: Context,
        catalog: MomentumAgentCatalog,
    ) -> ResearchOutcome:
        for round_number in range(self._reports.request.max_debate_rounds):
            await self._run_round(context, catalog, round_number + 1)
        plan = await context.run_node(
            catalog.agent("research_manager"),
            self._input(),
            run_id="research-manager",
        )
        return ResearchOutcome(
            reports=self._reports,
            bull_arguments=self._bulls,
            bear_arguments=self._bears,
            plan=ResearchPlan.model_validate(plan),
        )

    async def _run_round(
        self,
        context: Context,
        catalog: MomentumAgentCatalog,
        round_number: int,
    ) -> None:
        bull = await context.run_node(
            catalog.agent("bull"),
            self._input(),
            run_id=f"bull-round-{round_number}",
        )
        self._bulls.append(BullArgument.model_validate(bull))
        bear = await context.run_node(
            catalog.agent("bear"),
            self._input(),
            run_id=f"bear-round-{round_number}",
        )
        self._bears.append(BearArgument.model_validate(bear))

    def _input(self) -> dict:
        return {
            "reports": self._reports.model_dump(mode="json"),
            "bull_arguments": [item.model_dump(mode="json") for item in self._bulls],
            "bear_arguments": [item.model_dump(mode="json") for item in self._bears],
        }


class RiskDebate:
    """Run the three risk perspectives for a bounded number of rounds."""

    ROLES = ("aggressive", "conservative", "neutral")

    def __init__(self, trader: TraderOutcome) -> None:
        self._trader = trader
        self._arguments: dict[str, list] = {role: [] for role in self.ROLES}

    async def execute(
        self,
        context: Context,
        catalog: MomentumAgentCatalog,
    ) -> RiskOutcome:
        request = self._trader.research.reports.request
        for round_number in range(request.max_risk_discuss_rounds):
            await self._run_round(context, catalog, round_number + 1)
        return RiskOutcome(
            trader=self._trader,
            aggressive_arguments=self._arguments["aggressive"],
            conservative_arguments=self._arguments["conservative"],
            neutral_arguments=self._arguments["neutral"],
        )

    async def _run_round(
        self,
        context: Context,
        catalog: MomentumAgentCatalog,
        round_number: int,
    ) -> None:
        for role in self.ROLES:
            await self._run_role(context, catalog, role, round_number)

    async def _run_role(
        self,
        context: Context,
        catalog: MomentumAgentCatalog,
        role: str,
        round_number: int,
    ) -> None:
        output = await context.run_node(
            catalog.agent(role),
            self._input(),
            run_id=f"{role}-round-{round_number}",
        )
        schema = catalog.ROLE_SCHEMAS[role]
        self._arguments[role].append(schema.model_validate(output))

    def _input(self) -> dict:
        return {
            "trader": self._trader.model_dump(mode="json"),
            "aggressive_arguments": self._dump("aggressive"),
            "conservative_arguments": self._dump("conservative"),
            "neutral_arguments": self._dump("neutral"),
        }

    def _dump(self, role: str) -> list[dict]:
        return [item.model_dump(mode="json") for item in self._arguments[role]]
