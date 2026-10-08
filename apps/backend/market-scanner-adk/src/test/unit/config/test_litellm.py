"""Exercise the real ADK and GenAI transport against a gateway HTTP stub."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from google.adk.agents import LlmAgent
from google.adk.models import LlmRequest
from google.genai import types
from pydantic import ValidationError

from app.components.agents.market_scanner import agent as scanner
from app.config.llm import LiteLLMGatewayModel, create_model
from app.config.settings import Settings
from app.utils.error import ErrorCode, LiteLLMError
from test.report_fixtures import research_critique_payload, unsourced_analysis_payload
from test.unit.components.agents.test_regime_workflow import market_data, run_graph


def gateway_config(**overrides):
    return Settings(
        _env_file=None,
        GOOGLE_CLOUD_PROJECT="test-project",
        **(
            {
                "LITELLM_API_BASE": "https://gateway.example",
                "LITELLM_API_KEY": "sk-offline-test",
            }
            | overrides
        ),
    )


@pytest.mark.parametrize(
    "base",
    [
        "",
        "ftp://gateway.example",
        "https://user:secret@gateway.example",
        "https://gateway.example/v1",
        "https://gateway.example?key=secret",
    ],
)
def should_reject_invalid_gateway_urls(base):
    with pytest.raises(ValidationError, match="gateway root HTTP URL"):
        gateway_config(LITELLM_API_BASE=base)


def should_require_a_virtual_key():
    with pytest.raises(ValidationError, match="LITELLM_API_KEY"):
        gateway_config(LITELLM_API_KEY="")


def should_hide_secrets_in_configuration_validation_errors():
    import traceback

    marker = "sk-PRIVATE-CONFIGURATION-KEY"
    with pytest.raises(ValidationError) as raised:
        gateway_config(LITELLM_API_BASE="invalid", LITELLM_API_KEY=marker)
    assert marker not in str(raised.value)
    assert marker not in "".join(traceback.format_exception(raised.value))


def should_hide_virtual_key_when_startup_configuration_is_missing(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    marker = "sk-PRIVATE-STARTUP-KEY"
    result = subprocess.run(
        [sys.executable, "-c", "import app.config.settings"],
        cwd=tmp_path,
        env={
            "PYTHONPATH": str(Path(scanner.__file__).parents[4]),
            "DOCKER_ENV": "true",
            "LITELLM_API_BASE": "https://gateway.example",
            "LITELLM_API_KEY": marker,
        },
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert marker not in result.stderr


@pytest.mark.parametrize("base", ["http://gateway.example", "http://10.0.0.1:4000"])
def should_reject_plaintext_remote_gateways(base):
    with pytest.raises(ValidationError, match="HTTPS"):
        gateway_config(LITELLM_API_BASE=base)


@pytest.mark.parametrize("base", ["http://127.0.0.1:4000", "http://[::1]:4000"])
def should_allow_plaintext_loopback_gateways_for_local_development(base):
    assert gateway_config(LITELLM_API_BASE=base).LITELLM_API_BASE == base


@pytest.mark.parametrize("stream", [False, True])
async def should_hide_invalid_gateway_response_details(stream):
    marker = "PRIVATE-RESPONSE-WITH-sk-offline-test"

    async def respond(request):
        body = {
            "candidates": [
                {
                    "index": marker,
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Safe response"}],
                    },
                }
            ]
        }
        if stream:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text="data: " + json.dumps(body) + "\n\n",
            )
        return httpx.Response(200, json=body)

    model = create_model(gateway_config())
    model.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(respond),
    }
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="Hi")])]
    )
    try:
        with pytest.raises(LiteLLMError) as raised:
            _ = [
                response
                async for response in model.generate_content_async(
                    request, stream=stream
                )
            ]
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
    assert marker not in str(raised.value)


@pytest.mark.parametrize("stream", [False, True])
async def should_never_follow_gateway_redirects(monkeypatch, stream):
    requests = []

    async def redirect(request):
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": "https://unexpected.example"},
            json={"error": {"code": 307, "message": "Redirect"}},
        )

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda: httpx.MockTransport(redirect)
    )
    model = create_model(gateway_config())
    # Exercise the factory's transport choice; do not override client_kwargs.
    assert not model.api_client._api_client._use_aiohttp()
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="Hi")])]
    )
    try:
        with pytest.raises(LiteLLMError):
            _ = [
                response
                async for response in model.generate_content_async(
                    request, stream=stream
                )
            ]
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
    assert len(requests) == 1
    assert requests[0].url.host == "gateway.example"


@pytest.mark.parametrize("call_tool", [False, True])
async def should_run_all_three_agents_through_native_gateway(monkeypatch, call_tool):
    data = market_data()
    requests = []
    outputs = [
        "Dated research.",
        json.dumps(research_critique_payload()),
        json.dumps(unsourced_analysis_payload(data.assets)),
    ]
    if call_tool:
        outputs.insert(0, None)
        from app.components.tools import market_research

        monkeypatch.setattr(
            market_research.research_client,
            "get_global_news",
            AsyncMock(return_value={"status": "empty", "items": []}),
        )

    async def respond(request):
        assert request.url.host == "gateway.example"
        assert request.url.path == "/v1beta/models/gemini-3.8-flash:generateContent"
        assert "sk-offline-test" not in str(request.url)
        assert request.headers["authorization"] == "Bearer sk-offline-test"
        requests.append(json.loads(request.content))
        output = outputs[len(requests) - 1]
        part = (
            {"text": output}
            if output is not None
            else {
                "functionCall": {"name": "get_global_news", "args": {}},
            }
        )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [part]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 30,
                },
            },
        )

    model = create_model(gateway_config())
    model.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(respond),
    }
    for agent in scanner.root_agent.graph.nodes:
        if isinstance(agent, LlmAgent):
            monkeypatch.setattr(agent, "model", model)
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    save = AsyncMock()
    monkeypatch.setattr(
        "app.services.market_scan_persistence.MarketScanPersistence.save", save
    )
    try:
        _, final = await run_graph()
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()

    assert len(requests) == 3 + int(call_tool)
    assert any("googleSearch" in tool for tool in requests[0]["tools"])
    assert [
        r["generationConfig"]["thinkingConfig"]["thinking_level"] for r in requests
    ] == ["MEDIUM"] * (2 + int(call_tool)) + ["LOW"]
    assert all(
        r["generationConfig"]["responseMimeType"] == "application/json"
        for r in requests[-2:]
    )
    if call_tool:
        assert any(
            "functionResponse" in part
            for content in requests[1]["contents"]
            for part in content["parts"]
        )
        assert final.state["research_tool_results"]
    assert final.state["research_critique"] == research_critique_payload()
    save.assert_awaited_once()
    assert (
        save.call_args.args[0].model_dump(mode="json")
        == (final.state["market_data"]["market_regime"])
    )


def should_hide_virtual_key_from_model_and_settings_representation():
    config = gateway_config()
    assert "sk-offline-test" not in repr(config)
    assert "sk-offline-test" not in repr(create_model(config))


@pytest.mark.parametrize("status", [401, 403, 429, 503, None])
async def should_propagate_gateway_failure_without_calling_vertex(status):
    calls = []

    async def reject(request):
        calls.append(request)
        assert request.url.host == "gateway.example"
        if status is None:
            raise httpx.ReadTimeout("PRIVATE upstream body sk-offline-test")
        return httpx.Response(
            status,
            json={
                "error": {
                    "code": status,
                    "message": "PRIVATE upstream body sk-offline-test",
                    "status": "UNAVAILABLE",
                }
            },
        )

    model = create_model(gateway_config())
    model.client_kwargs["http_options"].retry_options = types.HttpRetryOptions(
        attempts=1
    )
    model.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(reject),
    }
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="Hi")])]
    )
    try:
        with pytest.raises(LiteLLMError) as raised:
            _ = [response async for response in model.generate_content_async(request)]
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
    assert len(calls) == 1
    assert raised.value.error_code is ErrorCode.LITELLM_ERROR
    assert raised.value.status_code == 502
    if status is not None:
        assert raised.value.details["upstream_status"] == status
    else:
        assert raised.value.details == {"error_type": "ReadTimeout"}
    assert "PRIVATE" not in str(raised.value)
    assert "sk-offline-test" not in json.dumps(raised.value.to_dict())


@pytest.mark.parametrize("route", ["/run", "/run_sse"])
@pytest.mark.parametrize("failure", ["http", "invalid_response"])
async def should_expose_custom_error_over_adk_http_without_persisting(
    monkeypatch, caplog, route, failure
):
    from app.application import create_app
    from app.config.settings import settings
    from app.services.market_data_collection_service import MarketDataCollectionService

    calls = []

    async def reject(request):
        calls.append(request)
        if failure == "invalid_response":
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "index": "PRIVATE body sk-offline-test",
                            "content": {
                                "role": "model",
                                "parts": [{"text": "Safe response"}],
                            },
                        }
                    ]
                },
            )
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "message": "PRIVATE body sk-offline-test",
                    "status": "PERMISSION_DENIED",
                }
            },
        )

    probe = create_model(gateway_config())
    probe.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(reject)
    }
    api_client = probe.api_client
    monkeypatch.setattr(
        LiteLLMGatewayModel, "api_client", property(lambda _self: api_client)
    )
    data = market_data()
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda _self: data)
    monkeypatch.setattr(settings, "MARKET_SCANNER_TOKEN", "")
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://scanner"
        ) as client:
            session = await client.post(
                "/apps/market_scanner/users/gateway-test/sessions", json={"state": {}}
            )
            response = await client.post(
                route,
                json={
                    "appName": "market_scanner",
                    "userId": "gateway-test",
                    "sessionId": session.json()["id"],
                    "newMessage": {"role": "user", "parts": [{"text": "Scan"}]},
                },
            )
    finally:
        await api_client.aio.aclose()
        api_client.close()
    if route == "/run":
        assert response.status_code == 502
        assert response.json() == {"error": "LiteLLM gateway request failed"}
    else:
        assert response.status_code == 200
        assert "LiteLLMError" in response.text
        assert "LITELLM_ERROR" in response.text
    assert len(calls) == 1
    save.assert_not_awaited()
    for text in [response.text, caplog.text]:
        assert "PRIVATE body" not in text
        assert "sk-offline-test" not in text


async def should_fail_scheduled_worker_with_custom_code_and_no_persistence(
    monkeypatch, caplog
):
    from app.config.settings import settings
    from app.jobs import daily_scan

    calls = []

    async def reject(request):
        calls.append(request)
        assert request.url.host == "gateway.example"
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "message": "PRIVATE body",
                    "status": "PERMISSION_DENIED",
                }
            },
        )

    model = create_model(gateway_config())
    model.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(reject),
    }
    for agent in scanner.root_agent.graph.nodes:
        if isinstance(agent, LlmAgent):
            monkeypatch.setattr(agent, "model", model)
    data = market_data()
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    monkeypatch.setattr(daily_scan, "root_agent", scanner.root_agent)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://offline-test")
    monkeypatch.setattr(daily_scan, "close_database", AsyncMock())
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)
    try:
        assert await daily_scan.main() == 1
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
    assert len(calls) == 1
    save.assert_not_awaited()
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "scheduled_scan.failed"
    )
    assert record.error_type == "LiteLLMError"
    assert record.error_code == "LITELLM_ERROR"
    assert "PRIVATE body" not in caplog.text


async def should_stream_native_response_from_gateway():
    async def respond(request):
        assert request.url.path.endswith(":streamGenerateContent")
        assert request.url.params["alt"] == "sse"
        assert request.headers["authorization"] == "Bearer sk-offline-test"
        result = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Stream result"}],
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="data: " + json.dumps(result) + "\n\n",
        )

    model = create_model(gateway_config())
    model.client_kwargs["http_options"].async_client_args = {
        "transport": httpx.MockTransport(respond),
    }
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="Hi")])]
    )
    try:
        responses = [
            response
            async for response in model.generate_content_async(request, stream=True)
        ]
    finally:
        await model.api_client.aio.aclose()
        model.api_client.close()
    assert any(
        part.text == "Stream result"
        for response in responses
        if response.content
        for part in response.content.parts
    )
