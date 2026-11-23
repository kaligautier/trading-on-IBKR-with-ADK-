"""Assemble a fresh MCP server with explicit component registration."""

import logging

from fastmcp import FastMCP
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools

from app import __version__
from app.auth import create_auth
from app.config.settings import Settings
from app.core_components.prompts import register_prompts
from app.core_components.resources import register_resources
from app.core_components.tools.portfolio_tools import register_portfolio_tools
from app.lifespan import api_lifespan
from app.routes.health import register_health


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings if settings is not None else Settings()
    server = FastMCP(
        name=settings.name,
        version=__version__,
        instructions=(
            "Read-only IBKR portfolio tools backed by the Deepcopy API. "
            "Read guide://deepcopy first, or use review_portfolio for a reusable "
            "portfolio prompt. No tool places orders."
        ),
        auth=create_auth(settings),
        mask_error_details=True,
        strict_input_validation=True,
        list_page_size=settings.page_size,
        lifespan=api_lifespan(settings),
    )
    server.add_middleware(
        LoggingMiddleware(
            logger=logging.getLogger("app.mcp.requests"),
            include_payloads=settings.log_tool_arguments,
            max_payload_length=settings.log_max_payload_length,
            methods=["tools/call"],
        )
    )
    if settings.deepcopy_api is not None:
        register_portfolio_tools(server)
    register_resources(server)
    register_prompts(server)
    register_health(server)
    if settings.resources_as_tools:
        server.add_transform(ResourcesAsTools(server))
    if settings.prompts_as_tools:
        server.add_transform(PromptsAsTools(server))
    return server
