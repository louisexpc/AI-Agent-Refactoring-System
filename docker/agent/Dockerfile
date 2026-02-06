# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      docker-cli \
      build-essential \
      git \
 && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-install-project --no-python-downloads

COPY orchestrator/ ./orchestrator/
COPY runner/ ./runner/

RUN uv sync --frozen --no-python-downloads

VOLUME ["/workspace"]

CMD ["uv", "run", "python", "orchestrator/agent_tool_workflow.py"]
# CMD ['bash']
