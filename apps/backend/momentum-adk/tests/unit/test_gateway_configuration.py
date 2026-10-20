"""Real GenAI serialization goes only to the configured native gateway."""

import httpx
import pytest
from google.adk.models import LlmRequest
from google.genai import types
from pydantic import ValidationError

from app.config.llm import LiteLLMError, create_model
from app.config.settings import Settings


@pytest.mark.parametrize(
    "url", ["", "https://user:pass@host", "https://host/v1", "http://host"]
)
def test_rejects_unsafe_gateway(url):
    with pytest.raises(ValidationError) as error:
        Settings(LITELLM_API_BASE=url, LITELLM_API_KEY="private-marker")
    assert "private-marker" not in str(error.value)


@pytest.mark.parametrize("status", [200, 401, 429, 500, 302])
async def test_native_gateway_transport(status):
    config = Settings(
        LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test-key"
    )
    model = create_model(config, "gemini-3.8-flash")
    calls = []

    async def respond(request):
        calls.append(request)
        assert request.url.host == "gateway.example"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert ":generateContent" in request.url.path
        return httpx.Response(
            status,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "verified"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
            headers={"location": "https://forbidden.example"},
        )

    model.client_kwargs["http_options"].async_client_args["transport"] = (
        httpx.MockTransport(respond)
    )
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="test")])]
    )
    try:
        if status == 200:
            results = [item async for item in model.generate_content_async(request)]
            assert results[0].content.parts[0].text == "verified"
        else:
            with pytest.raises(LiteLLMError):
                _ = [item async for item in model.generate_content_async(request)]
        assert calls
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
