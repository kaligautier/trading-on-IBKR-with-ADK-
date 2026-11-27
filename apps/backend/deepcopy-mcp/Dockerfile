FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
ARG INSTALL_TELEMETRY=false
COPY --from=ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_TELEMETRY" = "true" ]; then \
        uv sync --frozen --no-dev --no-install-project --extra telemetry; \
    else uv sync --frozen --no-dev --no-install-project; fi
COPY src/app ./src/app
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_TELEMETRY" = "true" ]; then \
        uv sync --frozen --no-dev --no-editable --extra telemetry; \
    else uv sync --frozen --no-dev --no-editable; fi

FROM base AS runtime
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=builder /app/.venv /app/.venv
COPY --chmod=755 start_server.sh /app/start_server.sh
ENV PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT=8000 \
    MCP_ENVIRONMENT=production FASTMCP_LOG_ENABLED=false
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
ENTRYPOINT ["/app/start_server.sh"]
