"""Opt-in live native API and access-control smoke test (billable requests)."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from google.genai import Client, types
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "infra/litellm/scripts"))
import bootstrap_scanner_key as b  # noqa: E402


class Result(BaseModel):
    gateway_ok: bool


async def main():
    b.validate_configuration()
    key = b.gcloud("secrets", "versions", "access", "latest", "--secret=" + b.SECRET)
    headers = b.iap_headers(key)
    with httpx.Client(base_url=b.BASE_URL, headers=headers, timeout=180) as client:
        for route, body in [
            ("/key/generate", {}),
            (
                "/v1beta/models/forbidden-model:generateContent",
                {"contents": [{"parts": [{"text": "Hi"}]}]},
            ),
        ]:
            r = client.post(route, json=body)
            print("Denied route", route, r.status_code, flush=True)
            assert r.status_code == 403
        r = client.post(
            "/v1beta/models/gemini-3.8-flash:generateContent",
            headers={"Proxy-Authorization": ""},
            json={"contents": [{"parts": [{"text": "Hi"}]}]},
        )
        print("No IAP", r.status_code, flush=True)
        assert r.status_code in (401, 403)
    # Explicitly select the Gemini API shape even when the scanner uses Vertex.
    with Client(
        vertexai=False,
        api_key=key,
        http_options=types.HttpOptions(
            base_url=b.BASE_URL,
            api_version="v1beta",
            headers=b.iap_headers(key),
            timeout=180_000,
            retry_options=types.HttpRetryOptions(attempts=1),
            client_args={"follow_redirects": False},
            async_client_args={
                "follow_redirects": False,
                "transport": httpx.AsyncHTTPTransport(),
            },
        ),
    ) as model:
        async with model.aio as client:
            result = await client.models.generate_content(
                model=b.MODELS[0],
                contents="Return gateway_ok true.",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Result,
                    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                ),
            )
            assert json.loads(result.text) == {"gateway_ok": True}
            print(
                "Native schema + thinking: OK",
                result.usage_metadata.total_token_count,
                flush=True,
            )
            research = await client.models.generate_content(
                model=b.MODELS[0],
                contents=(
                    "Search the web for the official Google Gemini documentation. "
                    "Give one sentence and its source."
                ),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
                ),
            )
            grounding = research.candidates[0].grounding_metadata
            print(
                "Search grounding:",
                bool(grounding),
                "chunks:",
                len(grounding.grounding_chunks or []) if grounding else 0,
                flush=True,
            )
            assert grounding and grounding.grounding_chunks
            stream = await client.models.generate_content_stream(
                model=b.MODELS[0], contents="Reply only STREAM_OK."
            )
            output = ""
            async for chunk in stream:
                output += chunk.text or ""
            assert "STREAM_OK" in output
            print("Native streaming: OK", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
