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
            return self.reject(body, "MCP-Protocol-Version is required.")
        version = request.headers["mcp-protocol-version"]
        if version != VERSION:
            # FastMCP supports legacy handshake transports too. This endpoint
            # deliberately exposes only the requested stateless protocol.
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32022,
                        "message": "Unsupported protocol version.",
                        "data": {"requested": version, "supported": [VERSION]},
                    },
                },
                status_code=400,
                headers={"MCP-Protocol-Version": VERSION},
            )
        if not isinstance(info, dict) or not all(
            isinstance(info.get(key), str) for key in ("name", "version")
        ):
            return self.reject(
                body, "SEP-2575 requires clientInfo.name and version on every request."
            )
        return await call_next(request)

    @staticmethod
    def reject(body, message):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32602, "message": message},
            },
            status_code=400,
            headers={"MCP-Protocol-Version": VERSION},
        )


def create_http_app(server: FastMCP):
    return server.http_app(
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
            Middleware(RequireStatelessMetadata),
        ],
    )
