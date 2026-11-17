FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS builder

ENV UV_LINK_MODE=copy \
    SOURCE_DATE_EPOCH=1704067200

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --only-group build --no-install-project --no-build
COPY src/ ./src/
RUN uv build --wheel --no-build-isolation \
    && uv sync --locked --no-dev --no-install-project --no-build \
    && uv pip install --python /app/.venv/bin/python --no-deps --no-index dist/*.whl

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["momentum-public-mcp"]
