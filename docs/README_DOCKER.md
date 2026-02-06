# Docker MVP (v2) - matches current repo layout

## What this provides
- `refactor-orchestrator:latest`: runs `orchestrator/agent.py` using **uv** with `uv.lock`.
- `refactor-sandbox:latest`: base sandbox image for per-iteration clean containers.

## Expected repo layout (from your screenshot)
- `orchestrator/agent.py`
- `orchestrator/config.yaml`
- `orchestrator/prompts/*.md`
- `pyproject.toml`, `uv.lock`, `.python-version`

If `agent.py` imports from `core/`, `shared/`, etc., uncomment the COPY lines in `docker/agent/Dockerfile`.

## Build
```bash
docker compose build
```

## Run orchestrator
```bash
mkdir -p workspace
docker compose up -d orchestrator
docker compose logs -f orchestrator
```

## Workspace default (host)
`./workspace` is mounted to `/workspace` inside the orchestrator container.
Suggested default output convention (you can change later):
```
workspace/
  runs/
    <run_id>/
      repo/              # git clone/checkout here
      iters/
        001/
          artifacts/
          logs/
        002/
          ...
      summary/
```

## Notes about "entry"
The container's default **entry command** is:
`python orchestrator/agent.py --config orchestrator/config.yaml`.
If you later change the file/module that should be executed, update the Dockerfile `CMD`.
