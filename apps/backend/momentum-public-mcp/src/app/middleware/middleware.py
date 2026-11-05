"""Configure the public server's FastMCP middleware in execution order."""

from fastmcp import FastMCP
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware

from app.middleware.logging import RequestLoggingMiddleware
from app.security import FingerprintProvider


def configure_middleware(
    server: FastMCP, fingerprint: FingerprintProvider | None
) -> None:
    # The outer logger also observes requests rejected by the rate limiter.
    server.add_middleware(RequestLoggingMiddleware())
    if fingerprint is not None:
        server.add_middleware(
            SlidingWindowRateLimitingMiddleware(
                max_requests=60,
                window_minutes=1,
                get_client_id=lambda context: fingerprint.current(),
            )
        )
