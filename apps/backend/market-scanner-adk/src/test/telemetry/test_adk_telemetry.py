"""ADK model and tool spans reach the locked OpenTelemetry SDK, offline."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

EXPORTER = InMemorySpanExporter()
PROVIDER = TracerProvider()
PROVIDER.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(PROVIDER)

# ADK caches its tracer during import; install the exporter first.
from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models import BaseLlm, LlmResponse  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402


class OfflineModel(BaseLlm):
    async def generate_content_async(self, llm_request, stream=False):
        responded = any(
            part.function_response
            for content in llm_request.contents
            for part in content.parts or []
        )
        part = (
            types.Part(text="6")
            if responded
            else types.Part(
                function_call=types.FunctionCall(name="double", args={"value": 3})
            )
        )
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def double(value: int) -> int:
    """Return twice the supplied value."""
    return value * 2


@pytest.mark.telemetry
async def test_adk_exports_model_and_tool_spans():
    agent = LlmAgent(
        name="telemetry_compatibility",
        model=OfflineModel(model="offline-compatibility"),
        tools=[double],
    )
    async with InMemoryRunner(
        agent=agent, app_name="telemetry_compatibility"
    ) as runner:
        session = await runner.session_service.create_session(
            app_name="telemetry_compatibility", user_id="fixture"
        )
        events = [
            event
            async for event in runner.run_async(
                user_id="fixture",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text="Double 3")]
                ),
            )
        ]
    assert any(
        part.text == "6"
        for event in events
        if event.content
        for part in event.content.parts or []
    ), "ADK did not complete the tool round trip"
    spans = EXPORTER.get_finished_spans()
    assert any("call_llm" in span.name for span in spans), "Model spans are missing"
    assert any("double" in span.name for span in spans), "Tool spans are missing"
    assert all(span.context.is_valid for span in spans), "Invalid trace context"
    assert not any(span.status.status_code.name == "ERROR" for span in spans)
