"""Middleware installed on the public MCP entry point."""

from app.middleware.middleware import configure_middleware

__all__ = ["configure_middleware"]
