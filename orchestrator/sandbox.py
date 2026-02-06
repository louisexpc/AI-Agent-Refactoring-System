from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from typing import Any

from langchain_core.tools import tool

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

# =========================
# Sandbox tools (Docker SDK)
# =========================
# NOTE:
# - Core container lifecycle/exec/logs/build(image)
#  uses docker SDK (docker-py).
# - docker compose build is NOT natively
# supported by docker-py (compose v2 is a CLI plugin),
#   so we run `docker compose ...` via
# subprocess for that branch.


def _truncate(text: str, limit: int = 8000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...<truncated: {len(text) - limit} chars>..."


def _docker_client() -> docker.DockerClient:
    # Uses environment vars / default socket (e.g. /var/run/docker.sock).
    return docker.from_env()


def _encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _decode_bytes(b: bytes | None) -> str:
    if not b:
        return ""
    try:
        return b.decode("utf-8", errors="replace")
    except Exception:
        # last resort
        return str(b)


def _docker_compose_available() -> bool:
    # Compose v2 is typically `docker compose`, not `docker-compose`.
    return shutil.which("docker") is not None


def _run_compose(cmd: list[str], timeout_sec: int | None = None) -> dict[str, Any]:
    if not _docker_compose_available():
        return {"ok": False, "error": "docker CLI not found on PATH", "cmd": cmd}

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout_sec}s", "cmd": cmd}
    except Exception as exc:
        return {"ok": False, "error": f"compose exec error: {exc}", "cmd": cmd}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": _truncate(proc.stdout),
        "stderr": _truncate(proc.stderr),
        "cmd": cmd,
    }


@tool
def create_sandbox(
    image: str,
    name: str | None = None,
    binds: list[str] | None = None,
    workdir: str = "/workspace",
) -> str:
    """Creates a new sandbox container for an iteration (Docker SDK).

    Starts a detached container that stays alive (sleep infinity) so the agent can run
    multiple commands via `execute_command_in_sandbox`.

    Named-volume policy (enforced):
      - Always mount Docker named volume `workspace` at `/workspace` (rw),
        so orchestrator + sandboxes share the same data without relying on host paths.

    Args:
        image: Docker image to run (e.g., "refactor-sandbox:latest").
        name: Optional container name. If omitted, an auto name is generated.
        binds: Optional extra mounts in CLI-like format:
            ["/host/path:/container/path:rw", "volume_name:/container/path:rw", ...]
            Note: mounting anything to /workspace is rejected to preserve
            the enforced policy.
        workdir: Container working directory (default: /workspace).

    Returns:
        JSON string containing at least: {"sandbox_id": "...", "ok": bool, ...}
    """
    sandbox_id = name or f"sandbox-{uuid.uuid4().hex[:12]}"

    try:
        client = _docker_client()

        # docker-py volumes mapping:
        # - host path: {"/abs/host/path": {"bind": "/container/path", "mode": "rw"}}
        # - named volume: {"volume_name": {"bind": "/container/path", "mode": "rw"}}
        volumes: dict[str, dict[str, str]] = {
            # Enforced shared workspace (named volume)
            "workspace": {"bind": "/workspace", "mode": "rw"},
        }

        # Optional additional mounts (cannot override /workspace)
        if binds:
            for spec in binds:
                parts = spec.split(":")
                if len(parts) < 2:
                    continue

                src = parts[0].strip()
                dst = parts[1].strip()
                mode = (
                    parts[2].strip() if len(parts) >= 3 and parts[2].strip() else "rw"
                )

                # Enforce policy: /workspace is reserved
                # for the named volume.
                # Allow subpaths like /workspace/subdir? -> reject
                # as well to keep it simple.
                if dst == "/workspace" or dst.startswith("/workspace/"):
                    return _encode_payload(
                        {
                            "ok": False,
                            "sandbox_id": sandbox_id,
                            "stdout": "",
                            "stderr": _truncate(
                                f"Rejected bind mount to reserved path: {dst}. "
                                "Sandbox always mounts named volume "
                                "'workspace' at /workspace."
                            ),
                            "result_snapshot": {"error_type": "InvalidBindSpec"},
                        }
                    )

                volumes[src] = {"bind": dst, "mode": mode}

        container = client.containers.run(
            image=image,
            command=["sh", "-lc", "sleep infinity"],
            name=sandbox_id,
            detach=True,
            labels={"owner": "multi_agent"},
            working_dir=workdir,
            volumes=volumes,
        )

        payload = {
            "ok": True,
            "sandbox_id": sandbox_id,
            "stdout": _truncate(container.id),
            "stderr": "",
            "result_snapshot": {
                "container_id": container.id,
                "name": container.name,
                "image": image,
                "workdir": workdir,
                "volumes": volumes,
            },
        }
        return _encode_payload(payload)

    except ImageNotFound as exc:
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": _truncate(str(exc)),
                "result_snapshot": {"error_type": "ImageNotFound"},
            }
        )
    except (APIError, DockerException) as exc:
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": _truncate(str(exc)),
                "result_snapshot": {"error_type": type(exc).__name__},
            }
        )


@tool
def execute_command_in_sandbox(
    sandbox_id: str,
    command: str,
    workdir: str | None = None,
    timeout_sec: int = 600,
) -> str:
    """Executes a shell command inside an existing sandbox container (Docker SDK).

    Args:
        sandbox_id: Target container name/id returned by `create_sandbox`.
        command: Shell command to execute (runs via `sh -lc`).
        workdir: Optional working directory for the command.
        timeout_sec: Max execution time in seconds.

    Returns:
        JSON string: {"ok": bool, "exit_code": int, "stdout": str, "stderr": str}
    """

    def _parse_exec_result(exec_result: Any) -> tuple[int, str, str]:
        # Exit code may be None on some docker-py / engine combos.
        raw_code = getattr(exec_result, "exit_code", None)
        try:
            exit_code = int(raw_code) if raw_code is not None else 0
        except Exception:
            exit_code = 0

        out_text = ""
        err_text = ""

        output = getattr(exec_result, "output", None)

        # demux=True: output is (stdout_bytes, stderr_bytes)
        if isinstance(output, tuple) and len(output) == 2:
            out_b, err_b = output
            out_text = _truncate(_decode_bytes(out_b or b""))
            err_text = _truncate(_decode_bytes(err_b or b""))
            return exit_code, out_text, err_text

        # demux=False (or some versions): output is bytes
        if isinstance(output, (bytes, bytearray)):
            out_text = _truncate(_decode_bytes(bytes(output)))
            return exit_code, out_text, ""

        # Fallback: stringify anything else (best-effort)
        if output is not None:
            out_text = _truncate(str(output))

        return exit_code, out_text, err_text

    try:
        client = _docker_client()
        container = client.containers.get(sandbox_id)

        start = time.time()

        try:
            exec_result = container.exec_run(
                cmd=["sh", "-lc", command],
                workdir=workdir,
                demux=True,
            )
            exit_code, out_text, err_text = _parse_exec_result(exec_result)
        except TypeError:
            # Fallback if workdir not supported
            # by exec_run in the local docker-py version.
            exec_result = container.exec_run(
                cmd=["sh", "-lc", command],
                demux=True,
            )
            exit_code, out_text, err_text = _parse_exec_result(exec_result)

        # Soft timeout check (best-effort). If exceeded, report as timeout.
        elapsed = time.time() - start
        if elapsed > timeout_sec:
            return _encode_payload(
                {
                    "ok": False,
                    "exit_code": 124,
                    "stdout": out_text,
                    "stderr": _truncate(f"timeout after {timeout_sec}s"),
                }
            )

        return _encode_payload(
            {
                "ok": exit_code == 0,
                "exit_code": exit_code,
                "stdout": out_text,
                "stderr": err_text,
            }
        )

    except NotFound as exc:
        return _encode_payload(
            {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": _truncate(f"container not found: {exc}"),
            }
        )
    except (APIError, DockerException) as exc:
        return _encode_payload(
            {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": _truncate(str(exc)),
            }
        )


@tool
def remove_sandbox(sandbox_id: str, force: bool = True) -> str:
    """Stops and removes a sandbox container (Docker SDK)."""
    try:
        client = _docker_client()
        container = client.containers.get(sandbox_id)
        container.remove(force=force)

        return _encode_payload(
            {
                "ok": True,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": "",
            }
        )
    except NotFound:
        # Match CLI behavior: removing non-existing container is considered error-ish,
        # but you can decide to treat it as ok. Keep strict here.
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": "container not found",
            }
        )
    except (APIError, DockerException) as exc:
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": _truncate(str(exc)),
            }
        )


# =========================
# NEW Tool #1: read container output (logs)
# =========================


@tool
def read_sandbox_output(
    sandbox_id: str,
    tail: int = 200,
    since_sec: int | None = None,
    timestamps: bool = False,
) -> str:
    """Reads recent logs from a sandbox container.

    Args:
        sandbox_id: Target container name/id.
        tail: How many lines to tail (default: 200).
        since_sec: Only return logs since N seconds ago (best-effort).
        timestamps: Include timestamps if True.

    Returns:
        JSON string: {"ok": bool, "sandbox_id": str, "stdout": str, "stderr": str}
        - stdout holds the log text.
        - stderr holds errors (if any).
    """
    try:
        client = _docker_client()
        container = client.containers.get(sandbox_id)

        since = None
        if since_sec is not None and since_sec >= 0:
            since = int(time.time() - since_sec)

        logs = container.logs(
            tail=tail,
            since=since,
            timestamps=timestamps,
        )
        text = _truncate(_decode_bytes(logs))

        return _encode_payload(
            {
                "ok": True,
                "sandbox_id": sandbox_id,
                "stdout": text,
                "stderr": "",
            }
        )
    except NotFound as exc:
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": _truncate(f"container not found: {exc}"),
            }
        )
    except (APIError, DockerException) as exc:
        return _encode_payload(
            {
                "ok": False,
                "sandbox_id": sandbox_id,
                "stdout": "",
                "stderr": _truncate(str(exc)),
            }
        )


# =========================
# NEW Tool #2: build docker image OR docker compose build
# =========================


@tool
def build_docker_image_or_compose(
    mode: str,
    *,
    # Image build (SDK)
    context_path: str | None = None,
    dockerfile: str | None = None,
    tag: str | None = None,
    build_args: dict[str, str] | None = None,
    target: str | None = None,
    # Compose build (CLI)
    compose_file: str | None = None,
    project_dir: str | None = None,
    services: list[str] | None = None,
    no_cache: bool = False,
    pull: bool = False,
    timeout_sec: int = 1800,
) -> str:
    """Builds a Docker image (via Docker SDK) or runs `docker compose build` (via CLI).

    Args:
        mode: "image" or "compose"
        --- image mode ---
        context_path: build context directory.
        dockerfile: Dockerfile path relative to context (or absolute).
        tag: resulting image tag (e.g., "refactor-sandbox:latest").
        build_args: docker build args.
        target: multi-stage target name.
        --- compose mode ---
        compose_file: path to docker-compose.yml (or compose.yaml).
        project_dir: working directory for compose (defaults to current process cwd).
        services: optional list of services to build.
        no_cache: pass --no-cache
        pull: pass --pull
        timeout_sec: subprocess timeout for compose build.

    Returns:
        JSON string with consistent fields:
        - For mode="image": {"ok", "image_id", "stdout", "stderr", "result_snapshot"}
        - For mode="compose": {"ok", "returncode", "stdout", "stderr", "cmd"}
    """
    if mode not in {"image", "compose"}:
        return _encode_payload(
            {"ok": False, "error": "mode must be 'image' or 'compose'", "mode": mode}
        )

    if mode == "image":
        if not context_path or not tag:
            return _encode_payload(
                {
                    "ok": False,
                    "error": "context_path and tag are required for mode='image'",
                    "mode": mode,
                }
            )

        try:
            client = _docker_client()
            image_obj, logs_iter = client.images.build(
                path=context_path,
                dockerfile=dockerfile,
                tag=tag,
                buildargs=build_args,
                target=target,
                rm=True,
            )

            # logs_iter yields dict messages; capture a concise tail for LLM.
            collected: list[str] = []
            for chunk in logs_iter:
                # chunk examples: {"stream": "..."} or {"error": "..."}
                if "stream" in chunk:
                    collected.append(chunk["stream"])
                elif "error" in chunk:
                    collected.append(f"[ERROR] {chunk['error']}")
                elif "status" in chunk:
                    collected.append(f"{chunk.get('status')}\n")
                if sum(len(x) for x in collected) > 12000:
                    break

            stdout = _truncate("".join(collected), limit=8000)
            return _encode_payload(
                {
                    "ok": True,
                    "image_id": image_obj.id,
                    "stdout": stdout,
                    "stderr": "",
                    "result_snapshot": {"tag": tag},
                }
            )
        except (APIError, DockerException) as exc:
            return _encode_payload(
                {
                    "ok": False,
                    "image_id": "",
                    "stdout": "",
                    "stderr": _truncate(str(exc)),
                    "result_snapshot": {
                        "tag": tag or "",
                        "error_type": type(exc).__name__,
                    },
                }
            )

    # mode == "compose"
    if not compose_file:
        return _encode_payload(
            {"ok": False, "error": "compose_file is required for mode='compose'"}
        )

    cmd: list[str] = ["docker", "compose", "-f", compose_file, "build"]
    if no_cache:
        cmd.append("--no-cache")
    if pull:
        cmd.append("--pull")
    if services:
        cmd.extend(services)

    result = _run_compose(cmd, timeout_sec=timeout_sec)
    # include project_dir if provided (subprocess cwd)
    if project_dir:
        # rerun with cwd (safer than trying to “edit” result)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
                cwd=project_dir,
            )
            result = {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": _truncate(proc.stdout),
                "stderr": _truncate(proc.stderr),
                "cmd": cmd,
                "cwd": project_dir,
            }
        except subprocess.TimeoutExpired:
            result = {
                "ok": False,
                "error": f"timeout after {timeout_sec}s",
                "cmd": cmd,
                "cwd": project_dir,
            }
        except Exception as exc:
            result = {
                "ok": False,
                "error": f"compose exec error: {exc}",
                "cmd": cmd,
                "cwd": project_dir,
            }

    return _encode_payload(result)
