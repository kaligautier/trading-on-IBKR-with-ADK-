"""CLI entry point for local STDIO or remote Streamable HTTP."""

import argparse

from app.application import create_server
from app.config.settings import Settings
from app.utils.logger import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MCP server template")
    parser.add_argument("--transport", choices=("stdio", "http"))
    args = parser.parse_args()
    settings = Settings(**({"transport": args.transport} if args.transport else {}))
    configure_logging(settings.log_level)
    server = create_server(settings)
    if settings.transport == "http":
        server.run(
            transport="http",
            host=settings.host,
            port=settings.port,
            path="/mcp",
            stateless_http=True,
            show_banner=False,
            host_origin_protection=True,
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
            uvicorn_config={"timeout_graceful_shutdown": 30},
        )
    else:
        server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
