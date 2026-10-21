"""Dynamic analyst fan-out for the Momentum workflow."""

import asyncio

from google.adk import Context

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.domain.contracts import AnalysisRequest, MemoryReflection
from app.domain.state import AnalystReports


class AnalystCoordinator:
    """Run selected analysts and memory reflections in isolated branches."""

    def __init__(self, catalog: MomentumAgentCatalog) -> None:
        self._catalog = catalog

    async def execute(
        self,
        context: Context,
        request: AnalysisRequest,
    ) -> AnalystReports:
        enriched_request, reflections = await self._reflect(context, request)
        roles = enriched_request.selected_analysts.values
        calls = [
            self._analyst_call(context, enriched_request, role.value) for role in roles
        ]
        outputs = await asyncio.gather(*calls)
        reports = AnalystReports(
            request=enriched_request,
            memory_reflections=reflections,
        )
        for role, output in zip(roles, outputs, strict=True):
            schema = self._catalog.ANALYST_SCHEMAS[role.value]
            setattr(reports, role.value, schema.model_validate(output))
        return reports

    def _analyst_call(
        self,
        context: Context,
        request: AnalysisRequest,
        role: str,
    ):
        return context.run_node(
            self._catalog.analyst_workflow(role),
            node_input=request.model_dump(mode="json"),
            run_id=f"analyst-{role}",
            use_sub_branch=True,
        )

    async def _reflect(
        self,
        context: Context,
        request: AnalysisRequest,
    ) -> tuple[AnalysisRequest, list[MemoryReflection]]:
        calls = [
            context.run_node(
                self._catalog.agent("reflection"),
                outcome.model_dump(mode="json"),
                run_id=f"reflection-{index}",
                use_sub_branch=True,
            )
            for index, outcome in enumerate(request.pending_outcomes, start=1)
        ]
        outputs = await asyncio.gather(*calls)
        reflections = self._reflections(request, outputs)
        enriched = request.model_copy(
            update={"past_context": self._memory_context(request, reflections)}
        )
        return enriched, reflections

    @staticmethod
    def _reflections(
        request: AnalysisRequest,
        outputs: list,
    ) -> list[MemoryReflection]:
        return [
            MemoryReflection(
                **outcome.model_dump(),
                reflection=output["reflection"],
            )
            for outcome, output in zip(request.pending_outcomes, outputs, strict=True)
        ]

    @staticmethod
    def _memory_context(
        request: AnalysisRequest,
        reflections: list[MemoryReflection],
    ) -> str:
        lessons = [item.reflection for item in reflections]
        return "\n\n".join(filter(None, [request.past_context, *lessons]))
