# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install uv binaries (Astral recommended pattern)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy lockfiles first for better caching
COPY pyproject.toml uv.lock .python-version ./

# Build tools + git for tree-sitter and snapshot clone
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      build-essential \
      git \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies (reproducible)
RUN uv sync --frozen --no-install-project

# Copy application code
COPY api/ ./api/
COPY core/ ./core/
COPY runner/ ./runner/
COPY shared/ ./shared/
COPY scripts/ ./scripts/

# Install project (if pyproject defines it)
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
