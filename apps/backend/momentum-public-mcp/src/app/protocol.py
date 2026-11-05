"""Configure FastMCP HTTP transport, CORS and OpenTelemetry."""

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.observability.telemetry import instrument_app


def create_http_app(server: FastMCP):
    app = server.http_app(
        path="/",
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["POST", "GET"],
                allow_headers=[
                    "Content-Type",
                    "MCP-Protocol-Version",
                    "Mcp-Method",
                    "Mcp-Name",
                ],
                expose_headers=["MCP-Protocol-Version"],
            ),
        ],
    )
    return instrument_app(app)
