"""Strict SEP-2575 profile on top of FastMCP's dual-era HTTP transport.

The current MCP spec makes clientInfo optional; the requested SEP requires it.
Reject legacy/headerless traffic rather than silently selecting a handshake era.
All dispatch, capabilities and protocol negotiation remain owned by FastMCP.
"""

import json

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from momentum_public_mcp.observability import RequestTelemetry
from momentum_public_mcp.utils.error import ErrorCode, ProtocolError

PREFIX = "io.modelcontextprotocol/"
VERSION = "2026-07-28"


class RequireStatelessMetadata(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method != "POST" or request.url.path != "/":
            return await call_next(request)
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return await call_next(request)  # SDK returns the JSON-RPC parse error.
        if not isinstance(body, dict) or "id" not in body:
            return await call_next(request)
        params = body.get("params")
        meta = params.get("_meta") if isinstance(params, dict) else None
        info = meta.get(PREFIX + "clientInfo") if isinstance(meta, dict) else None
        if not request.headers.get("mcp-protocol-version"):
            return self.reject(body, ProtocolError(ErrorCode.PROTOCOL_VERSION_REQUIRED))
        version = request.headers["mcp-protocol-version"]
        if version != VERSION:
            # FastMCP supports legacy handshake transports too. This endpoint
            # deliberately exposes only the requested stateless protocol.
            return self.reject(
                body,
                ProtocolError(
                    ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
                    data={"requested": version, "supported": [VERSION]},
                ),
            )
        if not isinstance(info, dict) or not all(
            isinstance(info.get(key), str) for key in ("name", "version")
        ):
            return self.reject(body, ProtocolError(ErrorCode.CLIENT_INFO_REQUIRED))
        return await call_next(request)

    @staticmethod
    def reject(body, error: ProtocolError):
        return JSONResponse(
            error.to_jsonrpc(body.get("id")),
            status_code=error.status_code,
            headers={"MCP-Protocol-Version": VERSION},
        )


def create_http_app(server: FastMCP, **telemetry_options):
    return server.http_app(
        path="/",
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(RequestTelemetry, **telemetry_options),
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
                expose_headers=["MCP-Protocol-Version", "X-Request-ID"],
            ),
            Middleware(RequireStatelessMetadata),
        ],
    )
