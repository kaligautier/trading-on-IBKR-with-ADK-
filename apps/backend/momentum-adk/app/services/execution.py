"""Application service for direct Momentum ADK executions."""

import time

from app.domain.contracts import AnalysisRequest, WorkflowExecution


class MomentumExecutionService:
    """Enrich one command with memory and execute it through ADK."""

    def __init__(self, engine, memory_log) -> None:
        self._engine = engine
        self._memory_log = memory_log

    async def execute(self, request: AnalysisRequest) -> WorkflowExecution:
        started_at = time.monotonic()
        enriched_request = self._memory_log.prepare(request)
        execution = await self._engine.execute(
            enriched_request,
            invocation_id=request.invocation_id,
        )
        self._complete_statistics(execution, request, started_at)
        self._memory_log.complete(request, execution.result)
        return execution

    @staticmethod
    def _complete_statistics(
        execution: WorkflowExecution,
        request: AnalysisRequest,
        started_at: float,
    ) -> None:
        analyst_count = len(request.selected_analysts.values)
        statistics = execution.result.run_stats
        statistics.agents_total = analyst_count + 8
        statistics.agents_completed = statistics.agents_total
        statistics.reports_total = analyst_count + 3
        statistics.reports_completed = statistics.reports_total
        statistics.duration_seconds = round(time.monotonic() - started_at, 2)
