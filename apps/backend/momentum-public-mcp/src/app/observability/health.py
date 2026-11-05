"""Process liveness, independent of upstream API availability."""

from starlette.responses import JSONResponse


async def health_check(request) -> JSONResponse:
    """Return process liveness without exposing application data."""
    return JSONResponse({"status": "healthy", "service": "momentum-public-mcp"})
