"""Smoke test for Docker sandbox tools (LangGraph/LC tools).

This script tests only the three LangGraph tools
added for Docker sandbox control:
  - create_sandbox
  - execute_command_in_sandbox
  - remove_sandbox

Steps:
  1) Create a sandbox container
  2) Run a Python hello-world command in the sandbox
  3) Remove the sandbox container

Usage (inside orchestrator container):
  SANDBOX_IMAGE=refactor-sandbox:latest
  uv run python /app/orchestrator/test_v2.py

Notes:
  - These tools are LangChain/LangGraph tools (StructuredTool).
  They are NOT directly callable.
    Use `.invoke({...})` (preferred) or `.run(...)`
    depending on your installed versions.
  - Requires Docker CLI available in the orchestrator container,
  and docker socket mounted:
    `/var/run/docker.sock:/var/run/docker.sock`.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict


def _load_tool_response(raw: str) -> Dict[str, Any]:
    """Parses the JSON string returned by tools.

    Args:
        raw: JSON string returned from a tool.

    Returns:
        Parsed dictionary.

    Raises:
        ValueError: If `raw` is not valid JSON.
    """
    return json.loads(raw)


def _invoke_tool(tool_obj: Any, **kwargs: Any) -> str:
    """Invokes a LangChain/LangGraph tool safely across versions.

    LangChain tools are typically `StructuredTool` instances and must be called via
    `.invoke(input_dict)` (newer) or `.run(**kwargs)` (older convenience).

    Args:
        tool_obj: The tool instance.
        **kwargs: Tool arguments.

    Returns:
        Tool return value (expected to be a JSON string in this project).
    """
    if hasattr(tool_obj, "invoke"):
        # Newer LC tools API: input must be a single dict.
        return tool_obj.invoke(kwargs)  # type: ignore[no-any-return]
    if hasattr(tool_obj, "run"):
        return tool_obj.run(**kwargs)  # type: ignore[no-any-return]
    raise TypeError(f"Tool object does not support invoke/run: {type(tool_obj)!r}")


def main() -> int:
    """Runs the smoke test.

    Returns:
        Process exit code (0 for success).
    """
    image = os.getenv("SANDBOX_IMAGE", "refactor-sandbox:latest")

    # Import tools from your existing module.
    # This import assumes `test_v2.py` sits in
    # `orchestrator/` alongside `sandbox.py`.
    try:
        from sandbox import (
            create_sandbox,
            execute_command_in_sandbox,
            remove_sandbox,
        )
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] Could not import sandbox tools: {e}", file=sys.stderr)
        return 2

    sandbox_id: str | None = None
    try:
        print(f"[INFO] Creating sandbox from image: {image}")
        raw = _invoke_tool(create_sandbox, image=image)
        resp = _load_tool_response(raw)
        if not resp.get("ok"):
            print(f"[FAIL] create_sandbox failed: {resp}", file=sys.stderr)
            return 1

        sandbox_id = str(resp.get("sandbox_id") or "")
        if not sandbox_id:
            print(
                f"[FAIL] create_sandbox did not return sandbox_id: {resp}",
                file=sys.stderr,
            )
            return 1

        print(f"[INFO] Sandbox created: {sandbox_id}")

        # Use python3; fall back to python3.12
        # if python3 isn't available.
        # cmd = r'python3 -c "print(\"hello world\")" ||\
        #      python3.12 -c "print(\"hello world\")"'
        # 查詢資料夾
        cmd_search = r"ls /workspace/"
        print("[INFO] Executing search command in sandbox...")
        raw = _invoke_tool(
            execute_command_in_sandbox,
            sandbox_id=sandbox_id,
            command=cmd_search,
            timeout_sec=60,
        )
        search_resp = _load_tool_response(raw)
        if not search_resp.get("ok") or int(search_resp.get("exit_code", 1)) != 0:
            print(
                f"[FAIL] execute_command_in_sandbox \nfailed \
                : \n{search_resp}\nCommand: {cmd_search}",
                file=sys.stderr,
            )
            return 1
        print(f"[PASS] Search stdout: {search_resp.get('stdout', '').strip()}")
        fix_prefix = r"/workspace/project_1/stage_1/stage_plan/test_result/golden/"
        cmd_execute_golden = rf"sh {fix_prefix}execute_golden.sh"
        print("[INFO] Executing golden command in sandbox...")
        raw = _invoke_tool(
            execute_command_in_sandbox,
            sandbox_id=sandbox_id,
            command=cmd_execute_golden,
            timeout_sec=600,
        )
        golden_resp = _load_tool_response(raw)
        if not golden_resp.get("ok") or int(golden_resp.get("exit_code", 1)) != 0:
            print(
                f"[FAIL] execute_command_in_sandbox failed:\
                      {golden_resp}\nCommand: {cmd_execute_golden}",
                file=sys.stderr,
            )
            return 1
        print(f"[PASS] Golden stdout: {golden_resp.get('stdout', '').strip()}")
        fix_prefix_test = r"/workspace/project_1/stage_1/stage_plan/test_result/test/"
        cmd_execute = rf"sh {fix_prefix_test}execute_test.sh"

        print("[INFO] Executing execute command in sandbox...")
        raw = _invoke_tool(
            execute_command_in_sandbox,
            sandbox_id=sandbox_id,
            command=cmd_execute,
            timeout_sec=600,
        )
        exec_resp = _load_tool_response(raw)

        if not exec_resp.get("ok") or int(exec_resp.get("exit_code", 1)) != 0:
            print(
                f"[FAIL] execute_command_in_sandbox failed:\
                      {exec_resp}\nCommand: {cmd_execute}",
                file=sys.stderr,
            )
            return 1

        print("[INFO] Executing execute command in sandbox...")
        stdout = str(exec_resp.get("stdout", ""))

        print(f"[PASS] stdout: {stdout.strip()}")
        return 0

    finally:
        if sandbox_id:
            print(f"[INFO] Removing sandbox: {sandbox_id}")
            try:
                raw = _invoke_tool(remove_sandbox, sandbox_id=sandbox_id, force=True)
                rm_resp = _load_tool_response(raw)
                if not rm_resp.get("ok"):
                    print(
                        f"[WARN] remove_sandbox reported failure: {rm_resp}",
                        file=sys.stderr,
                    )
            except Exception as e:  # pragma: no cover
                print(f"[WARN] remove_sandbox raised: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
