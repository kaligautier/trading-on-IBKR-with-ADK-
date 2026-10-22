from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.domain.contracts import AnalysisRequest, WorkflowResult
from app.services.runtime import MomentumAdkEngine


class InMemorySessionService:
    def __init__(self) -> None:
        self.sessions = {}

    async def get_session(self, *, app_name, user_id, session_id):
        return self.sessions.get((app_name, user_id, session_id))

    async def create_session(self, *, app_name, user_id, session_id, state=None):
        session = SimpleNamespace(id=session_id, state=state or {}, events=[])
        self.sessions[(app_name, user_id, session_id)] = session
        return session


class RecordingRunner:
    def __init__(self, output: dict) -> None:
        self.output = output
        self.calls = []

    async def run_async(self, **kwargs):
        self.calls.append(kwargs)
        yield SimpleNamespace(output=self.output, invocation_id="invocation-42")


def analysis_request() -> AnalysisRequest:
    return AnalysisRequest(
        ticker="NVDA",
        analysis_date=date(2026, 8, 2),
        requested_by="user-42",
        session_id=UUID("d33d8f79-6a90-4aad-a7d7-d990ed341c47"),
    )


def workflow_output() -> dict:
    return WorkflowResult(
        ticker="NVDA",
        analysis_date=date(2026, 8, 2),
        signal="Buy",
        final_decision="**Rating**: Buy",
        structured={},
        reports={},
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_first_execution_creates_job_scoped_session_and_sends_request():
    sessions = InMemorySessionService()
    runner = RecordingRunner(workflow_output())
    engine = MomentumAdkEngine(runner, sessions)

    execution = await engine.execute(analysis_request())

    assert execution.session_id == str(analysis_request().session_id)
    assert execution.invocation_id == "invocation-42"
    assert execution.result.signal == "Buy"
    assert runner.calls[0]["new_message"] is not None
    assert runner.calls[0]["invocation_id"] is None


@pytest.mark.asyncio
async def test_retry_resumes_invocation_without_new_user_message():
    sessions = InMemorySessionService()
    runner = RecordingRunner(workflow_output())
    engine = MomentumAdkEngine(runner, sessions)
    await sessions.create_session(
        app_name="momentum",
        user_id="user-42",
        session_id=str(analysis_request().session_id),
    )

    await engine.execute(analysis_request(), invocation_id="invocation-existing")

    assert runner.calls[0]["new_message"] is None
    assert runner.calls[0]["invocation_id"] == "invocation-existing"


@pytest.mark.asyncio
async def test_resume_counts_prior_and_new_events_only_for_this_invocation():
    from google.adk.events import Event
    from google.genai import types

    sessions = InMemorySessionService()
    session = await sessions.create_session(
        app_name="momentum",
        user_id="user-42",
        session_id=str(analysis_request().session_id),
    )

    def response(invocation, tokens):
        return Event(
            author="analyst",
            invocation_id=invocation,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=tokens,
                candidates_token_count=2,
            ),
        )

    session.events = [response("invocation-42", 10), response("other", 900)]

    class ResumingRunner(RecordingRunner):
        async def run_async(self, **kwargs):
            session.events.extend(
                [
                    response("invocation-42", 20),
                    Event(
                        author="analyst",
                        invocation_id="invocation-42",
                        content=types.Content(
                            parts=[
                                types.Part.from_function_response(
                                    name="get_stock_data",
                                    response={"result": "prices"},
                                )
                            ]
                        ),
                    ),
                ]
            )
            async for event in super().run_async(**kwargs):
                yield event

    engine = MomentumAdkEngine(ResumingRunner(workflow_output()), sessions)
    execution = await engine.execute(analysis_request(), invocation_id="invocation-42")
    stats = execution.result.run_stats
    assert (stats.llm_calls, stats.tool_calls, stats.tokens_in, stats.tokens_out) == (
        2,
        1,
        30,
        4,
    )
    # A completed invocation replay must not reset or duplicate its counters.
    replay = MomentumAdkEngine(RecordingRunner(workflow_output()), sessions)
    again = await replay.execute(analysis_request(), invocation_id="invocation-42")
    assert again.result.run_stats == stats
