"""Route ADK's native Gemini requests through the private LiteLLM gateway."""

import asyncio

import httpx
from google.adk.models import Gemini
from google.genai import errors, types
from pydantic import ValidationError

from app.config.settings import Settings
from app.utils.error import LiteLLMError


class LiteLLMGatewayModel(Gemini):
    """Translate provider failures into the application's typed error contract."""

    async def generate_content_async(self, llm_request, stream=False):
        try:
            async for response in super().generate_content_async(llm_request, stream):
                yield response
        except (
            errors.APIError,
            httpx.TransportError,
            asyncio.TimeoutError,
            ValidationError,
        ) as error:
            details = {"error_type": type(error).__name__}
            if isinstance(error, errors.APIError):
                details["upstream_status"] = error.code
            # ADK logs exceptions and returns str(error) over SSE. Vendor error
            # bodies may include prompts or credentials; keep only safe context.
            raise LiteLLMError(details=details) from None


def create_model(config: Settings) -> LiteLLMGatewayModel:
    """Use native Gemini transport, with no direct-provider fallback."""
    return LiteLLMGatewayModel(
        model=config.MODEL,
        client_kwargs={
            "enterprise": False,
            "vertexai": False,
            # SDK requires a key; only Authorization authenticates the gateway.
            "api_key": "litellm-proxy",
            "http_options": types.HttpOptions(
                base_url=config.LITELLM_API_BASE.rstrip("/"),
                api_version="v1beta",
                headers={
                    "Authorization": "Bearer "
                    + config.LITELLM_API_KEY.get_secret_value(),
                },
                timeout=180_000,
                client_args={"follow_redirects": False},
                # GenAI otherwise chooses aiohttp and ignores follow_redirects.
                async_client_args={
                    "transport": httpx.AsyncHTTPTransport(),
                    "follow_redirects": False,
                },
            ),
        },
    )
