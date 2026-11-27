"""Public process liveness probe: no configuration or token disclosure."""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


def register_health(server: FastMCP) -> None:
    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})
