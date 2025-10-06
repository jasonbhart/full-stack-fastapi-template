# syntax=docker/dockerfile:1.7
# Multi-stage build for optimized image size and security
# Stage 1: Builder stage
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Compile bytecode for better performance
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache configuration
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

# Install dependencies in a separate layer for better caching
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Runtime stage
FROM python:3.11-slim

# Security: Run as non-root user
RUN useradd -m -u 1000 app && \
    mkdir -p /app && \
    chown -R app:app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy application code
COPY --chown=app:app ./scripts /app/scripts
COPY --chown=app:app ./pyproject.toml ./uv.lock ./alembic.ini /app/
COPY --chown=app:app ./app /app/app

# Switch to non-root user
USER app

# Health check endpoint using stdlib
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/utils/health-check/', timeout=2)"

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
