FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
WORKDIR /app
RUN useradd --uid 10001 --create-home momentum
COPY --from=build --chown=10001:10001 /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    MOMENTUM_RESULTS_DIR=/tmp/momentum/logs MOMENTUM_CACHE_DIR=/tmp/momentum/cache \
    MOMENTUM_MEMORY_LOG_PATH=/tmp/momentum/memory.md
USER 10001
CMD ["python", "-m", "app.job_runner"]
