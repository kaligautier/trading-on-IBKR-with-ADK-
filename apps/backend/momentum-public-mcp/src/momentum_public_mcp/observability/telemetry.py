"""OpenTelemetry Cloud Trace configuration and ASGI instrumentation."""

import logging

from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from momentum_public_mcp.config.config import Settings

logger = logging.getLogger(__name__)


def init_telemetry(settings: Settings) -> TracerProvider:
    """Initialize tracing for every request, exporting when a GCP project is set."""
    tracer_provider = TracerProvider(sampler=ALWAYS_ON, shutdown_on_exit=False)

    if settings.GOOGLE_CLOUD_PROJECT:
        cloud_trace_exporter = CloudTraceSpanExporter(
            project_id=settings.GOOGLE_CLOUD_PROJECT,
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))

    trace.set_tracer_provider(tracer_provider)
    logger.info("OpenTelemetry initialized")
    return tracer_provider


def instrument_app(app):
    """Instrument the FastMCP ASGI app, excluding process health probes."""
    app = OpenTelemetryMiddleware(
        app,
        excluded_urls=r"/health(?:\?.*)?$",
        exclude_spans=["receive", "send"],
    )
    logger.info("ASGI app instrumented with OpenTelemetry")
    return app
