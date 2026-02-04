# syntax=docker/dockerfile:1
# Orchestrator (LangGraph) image - matches repo layout:
#   /orchestrator/agent.py
#   /orchestrator/config.yaml
#   /orchestrator/prompts/*.md
#
# Dependency management: uv (pyproject.toml + uv.lock + .python-version)
FROM python:3.12-slim

# Install uv binaries (Astral recommended pattern)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1         PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy lockfiles first for better caching
COPY pyproject.toml uv.lock .python-version ./

# Install dependencies (reproducible)
RUN uv sync --frozen --no-install-project

# Copy orchestrator code/config/prompts
COPY orchestrator/ ./orchestrator/

# If your orchestrator imports from other local packages (e.g., core/, shared/),
# add COPY lines below. Uncomment as needed:
# COPY core/ ./core/
# COPY shared/ ./shared/
# COPY api/ ./api/
# COPY runner/ ./runner/
# COPY spec/ ./spec/

# Install project (if pyproject defines it) - safe even if it's not a package
RUN uv sync --frozen

# Runtime workspace (repos/artifacts/logs) should be mounted here
VOLUME ["/workspace"]

# Default: run orchestrator agent with its config.
CMD ["uv", "run", "python", "/app/orchestrator/agent.py", "--config", "/app/orchestrator/config.yaml"]
