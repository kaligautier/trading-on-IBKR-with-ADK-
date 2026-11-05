"""Verify exported MCP/HTTP span trees and their correlated application logs."""

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode
from starlette.testclient import TestClient
from test_gateway import analysis_summary, market_scan
from test_stateless_http import envelope, headers

from app.application import MomentumPublicApplication
from app.config.config import Settings
from app.core_components.resources.public_resources import LATEST_MARKET_SCAN_URI
from app.protocol import create_http_app


@pytest.mark.parametrize("upstream_status", [200, 503])
def test_exported_span_tree_matches_http_calls(tracing, monkeypatch, upstream_status):
    provider, exporter = tracing
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/v1/market-scans/latest":
            return httpx.Response(200, json=market_scan())
        return httpx.Response(
            upstream_status,
            json={"items": [analysis_summary()], "next_page_token": ""},
        )

    original = httpx.AsyncClient

    class MockClient(original):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)
    app = MomentumPublicApplication(
        Settings(
            _env_file=None,
            SUGGESTION_HASH_SECRET="test-secret",
            MOMENTUM_API_USE_IAM=False,
            MOMENTUM_API_URL="https://momentum.test",
            MARKET_SCANNER_API_URL="https://scanner.test",
        )
    )
    parent_trace = "1" * 32
    with TestClient(create_http_app(app.mcp)) as client:
        response = client.post(
            "/",
            headers={
                **headers("tools/call", "momentum_list_analyses"),
                "traceparent": f"00-{parent_trace}-{'2' * 16}-01",
            },
            json=envelope(
                "tools/call",
                name="momentum_list_analyses",
                arguments={"ticker": "AAPL"},
            ),
        )
        assert response.status_code == 200
        assert bool(response.json()["result"].get("isError")) == (
            upstream_status == 503
        )
        for method, name, params in [
            ("resources/read", LATEST_MARKET_SCAN_URI, {"uri": LATEST_MARKET_SCAN_URI}),
            (
                "prompts/get",
                "momentum_analyze_ticker",
                {"name": "momentum_analyze_ticker", "arguments": {"ticker": "AAPL"}},
            ),
        ]:
            assert (
                client.post(
                    "/", headers=headers(method, name), json=envelope(method, **params)
                ).status_code
                == 200
            )
        provider.force_flush()
        before_health = len(exporter.get_finished_spans())
        assert client.get("/health").json()["status"] == "healthy"
        provider.force_flush()
        assert len(exporter.get_finished_spans()) == before_health

    spans = exporter.get_finished_spans()
    tool_spans = [
        s for s in spans if s.attributes.get("mcp.method.name") == "tools/call"
    ]
    assert len(tool_spans) == 1
    tool_span = tool_spans[0]
    assert format(tool_span.context.trace_id, "032x") == parent_trace
    by_id = {s.context.span_id: s for s in spans}
    server_span = by_id[tool_span.parent.span_id]
    assert (
        server_span.instrumentation_scope.name == "opentelemetry.instrumentation.asgi"
    )
    assert server_span.parent.span_id == int("2" * 16, 16)
    children = [
        s
        for s in spans
        if s.kind == SpanKind.CLIENT and s.parent.span_id == tool_span.context.span_id
    ]
    assert len(children) == 1
    assert calls[0].headers["traceparent"].split("-")[2] == format(
        children[0].context.span_id, "016x"
    )
    if upstream_status == 503:
        assert all(
            s.status.status_code == StatusCode.ERROR for s in [tool_span, children[0]]
        )
    methods = {s.attributes.get("mcp.method.name") for s in spans}
    assert {"tools/call", "resources/read", "prompts/get"} <= methods
    assert len(calls) == 2


def test_all_spans_are_recorded_even_with_an_unsampled_parent(tracing):
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    provider, exporter = tracing
    parent = TraceContextTextMapPropagator().extract(
        {"traceparent": f"00-{'1' * 32}-{'2' * 16}-00"}
    )
    with provider.get_tracer("test").start_as_current_span("child", context=parent):
        assert trace.get_current_span().get_span_context().trace_flags.sampled
    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].context.trace_id == int("1" * 32, 16)
    assert spans[0].parent.span_id == int("2" * 16, 16)


def test_cloud_exporter_configuration_flushes_on_shutdown(monkeypatch):
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.observability import telemetry

    exporter = InMemorySpanExporter()
    projects = []
    installed = []

    def cloud_exporter(*, project_id):
        projects.append(project_id)
        return exporter

    monkeypatch.setattr(telemetry, "CloudTraceSpanExporter", cloud_exporter)
    monkeypatch.setattr(trace, "set_tracer_provider", installed.append)
    settings = Settings(
        _env_file=None,
        SUGGESTION_HASH_SECRET="test-secret",
        GOOGLE_CLOUD_PROJECT="test-project",
    )
    provider = telemetry.init_telemetry(settings)
    assert installed == [provider] and projects == ["test-project"]
    with provider.get_tracer("test").start_as_current_span("shutdown-proof"):
        pass
    provider.shutdown()
    assert [span.name for span in exporter.get_finished_spans()] == ["shutdown-proof"]
    assert len(projects) == len(installed) == 1
