"""Route ADK's native Gemini requests through the private LiteLLM gateway."""

import asyncio
import json

import httpx
from google.adk.models import Gemini
from google.genai import errors, types
from pydantic import ValidationError

from app.config.settings import Settings
from app.utils.error import LiteLLMError

# LiteLLM answers 429 when an agent key's per-minute token or request quota is
# spent, and the quota resets within a minute. Waits of about 20, 40 and 60 s
# span that window and fit the 900 s job timeout. Other errors are not retried.
RATE_LIMIT_RETRY = types.HttpRetryOptions(
    attempts=4,
    initial_delay=20,
    max_delay=60,
    exp_base=2,
    http_status_codes=[429],
)


class LiteLLMGatewayModel(Gemini):
    """Translate provider failures into the application's typed error contract."""

    async def generate_content_async(self, llm_request, stream=False):
        try:
            async for response in super().generate_content_async(llm_request, stream):
                yield response
        except (
            errors.APIError,
            errors.UnknownApiResponseError,
            json.JSONDecodeError,
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
                retry_options=RATE_LIMIT_RETRY,
                client_args={"follow_redirects": False},
                # GenAI otherwise chooses aiohttp and ignores follow_redirects.
                async_client_args={
                    "transport": httpx.AsyncHTTPTransport(),
                    "follow_redirects": False,
                },
            ),
        },
    )
