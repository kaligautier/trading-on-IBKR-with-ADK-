"""Errors safe to expose across the API-to-MCP boundary."""


class UpstreamError(Exception):
    """A controlled error without credentials or raw upstream response bodies."""
