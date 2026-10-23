FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/app ./src/app
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83
RUN useradd --uid 10001 --create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chmod=755 start_server.sh /app/start_server.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
USER 10001
EXPOSE 8080
ENTRYPOINT ["/app/start_server.sh"]
