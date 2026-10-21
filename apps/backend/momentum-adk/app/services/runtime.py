"""Runner adapter for executing and resuming Momentum ADK workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.adk.apps import App, ResumabilityConfig
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from app.components.agents.momentum.workflow import MomentumWorkflowFactory
from app.config.llm import LiteLLMGatewayModel
from app.domain.contracts import (
    AnalysisRequest,
    RunStatistics,
    WorkflowExecution,
    WorkflowResult,
)
from app.infrastructure.session_database import create_session_service


class MomentumAdkEngine:
    """Execute one authenticated job through a reusable ADK Runner."""

    APP_NAME = "momentum"

    def __init__(self, runner: Any, session_service: Any) -> None:
        self._runner = runner
        self._session_service = session_service

    async def execute(
        self,
        request: AnalysisRequest,
        invocation_id: str | None = None,
    ) -> WorkflowExecution:
        user_id = request.requested_by or "system"
        session_id = str(request.session_id)
        await self._ensure_session(user_id, session_id, request)
        output, current_invocation_id = await self._run(
            request,
            user_id,
            session_id,
            invocation_id,
        )
        result = WorkflowResult.model_validate(output)
        session = await self._session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if session is None:
            raise RuntimeError("Momentum session disappeared after execution")
        # Persisted events include completed nodes replayed during resume.
        usage = RunStatistics()
        for event in session.events:
            if event.invocation_id != current_invocation_id or event.partial:
                continue
            if event.usage_metadata is not None:
                usage.llm_calls += 1
                usage.tokens_in += event.usage_metadata.prompt_token_count or 0
                usage.tokens_out += event.usage_metadata.candidates_token_count or 0
            usage.tool_calls += len(event.get_function_responses())
        for field in ("llm_calls", "tokens_in", "tokens_out", "tool_calls"):
            setattr(result.run_stats, field, getattr(usage, field))
        return WorkflowExecution(
            result=result,
            user_id=user_id,
            session_id=session_id,
            invocation_id=current_invocation_id,
        )

    async def _ensure_session(
        self,
        user_id: str,
        session_id: str,
        request: AnalysisRequest,
    ) -> None:
        existing = await self._session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if existing is not None:
            return
        await self._session_service.create_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"session_id": str(request.session_id), "ticker": request.ticker},
        )

    async def _run(
        self,
        request: AnalysisRequest,
        user_id: str,
        session_id: str,
        invocation_id: str | None,
    ) -> tuple[Any, str]:
        output = None
        current_invocation_id = invocation_id
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            invocation_id=invocation_id,
            new_message=self._new_message(request, invocation_id),
        ):
            if event.output is not None:
                output = event.output
            if event.invocation_id:
                current_invocation_id = event.invocation_id
        if output is None:
            raise RuntimeError("Momentum ADK workflow completed without output")
        if current_invocation_id is None:
            raise RuntimeError("Momentum ADK workflow did not expose an invocation id")
        return output, current_invocation_id

    @staticmethod
    def _new_message(
        request: AnalysisRequest,
        invocation_id: str | None,
    ) -> types.Content | None:
        if invocation_id is not None:
            return None
        return types.Content(
            role="user",
            parts=[types.Part.from_text(text=request.model_dump_json())],
        )


@dataclass(frozen=True, slots=True)
class MomentumRuntime:
    engine: MomentumAdkEngine
    session_service: DatabaseSessionService


class MomentumRuntimeFactory:
    """Create one reusable Runner and session service for the job process."""

    def __init__(
        self,
        quick_model: LiteLLMGatewayModel,
        deep_model: LiteLLMGatewayModel,
        session_database_url: str,
    ) -> None:
        self._quick_model = quick_model
        self._deep_model = deep_model
        self._session_database_url = session_database_url

    def application(self) -> App:
        root_agent = MomentumWorkflowFactory(
            quick_model=self._quick_model,
            deep_model=self._deep_model,
        ).create()
        return App(
            name=MomentumAdkEngine.APP_NAME,
            root_agent=root_agent,
            resumability_config=ResumabilityConfig(is_resumable=True),
        )

    async def create(self) -> MomentumRuntime:
        session_service = await create_session_service(self._session_database_url)
        runner = Runner(app=self.application(), session_service=session_service)
        return MomentumRuntime(
            engine=MomentumAdkEngine(runner, session_service),
            session_service=session_service,
        )
