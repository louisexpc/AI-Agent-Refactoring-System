from __future__ import annotations

import json
import shutil
import subprocess
import uuid

from langchain_core.tools import tool

# =========================
# Sandbox tools (Docker)
# =========================

# NOTE (added): These tools allow the Engineer agent to create an isolated
# container per iteration, run commands inside it, and tear it down.
# For MVP we intentionally use the Docker CLI via subprocess (no new deps).


def _docker_cli_available() -> bool:
    """Returns True if the Docker CLI is available on PATH."""

    return shutil.which("docker") is not None


def _truncate(text: str, limit: int = 8000) -> str:
    """Truncates long stdout/stderr for LLM consumption."""

    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...<truncated: {len(text) - limit} chars>..."


def _run_docker(cmd: list[str], timeout_sec: int | None = None) -> dict[str, object]:
    """Runs a docker CLI command and returns structured result."""

    if not _docker_cli_available():
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
        return {
            "ok": False,
            "error": f"timeout after {timeout_sec}s",
            "cmd": cmd,
        }
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": f"docker exec error: {exc}", "cmd": cmd}

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
    """Creates a new sandbox container for an iteration.

    This tool starts a detached container that stays alive (sleep) so the
    agent can run multiple commands via `execute_command_in_sandbox`.

    Args:
        image: Docker image to run (e.g., "sandbox:latest").
        name: Optional container name. If omitted, an auto name is generated.
        binds: Optional list of volume bind specs in Docker CLI format:
            ["/host/path:/container/path:rw", ...]
        workdir: Container working directory (default: /workspace).

    Returns:
        JSON string containing at least: {"sandbox_id": "...", "ok": bool, ...}
    """

    sandbox_id = name or f"sandbox-{uuid.uuid4().hex[:12]}"

    cmd: list[str] = [
        "docker",
        "run",
        "-d",
        "--name",
        sandbox_id,
        "--label",
        "owner=multi_agent",
        "-w",
        workdir,
    ]

    if binds:
        for b in binds:
            cmd.extend(["-v", b])

    # Keep the container alive for subsequent exec calls.
    cmd.extend([image, "sh", "-lc", "sleep infinity"])

    result = _run_docker(cmd)
    payload = {
        "ok": result.get("ok", False),
        "sandbox_id": sandbox_id,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "result_snapshot": result,
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def execute_command_in_sandbox(
    sandbox_id: str,
    command: str,
    workdir: str | None = None,
    timeout_sec: int = 600,
) -> str:
    """Executes a shell command inside an existing sandbox container.

    Args:
        sandbox_id: Target container name/id returned by `create_sandbox`.
        command: Shell command to execute (runs via `sh -lc`).
        workdir: Optional working directory for the command.
        timeout_sec: Max execution time in seconds.

    Returns:
        JSON string: {"ok": bool, "exit_code": int, "stdout": str, "stderr": str}
    """

    cmd: list[str] = ["docker", "exec"]
    if workdir:
        cmd.extend(["-w", workdir])
    cmd.extend([sandbox_id, "sh", "-lc", command])

    result = _run_docker(cmd, timeout_sec=timeout_sec)
    payload = {
        "ok": result.get("ok", False),
        "exit_code": int(result.get("returncode", 1)),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def remove_sandbox(sandbox_id: str, force: bool = True) -> str:
    """Stops and removes a sandbox container.

    Args:
        sandbox_id: Target container name/id.
        force: If True, use `docker rm -f` (default).

    Returns:
        JSON string: {"ok": bool, "sandbox_id": str, ...}
    """

    cmd = ["docker", "rm"]
    if force:
        cmd.append("-f")
    cmd.append(sandbox_id)

    result = _run_docker(cmd)
    payload = {
        "ok": result.get("ok", False),
        "sandbox_id": sandbox_id,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }
    return json.dumps(payload, ensure_ascii=False)
