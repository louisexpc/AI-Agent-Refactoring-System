from __future__ import annotations

import json
import os
from urllib import error, request

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _request_json(
    method: str, path: str, payload: dict | None = None
) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        return exc.code, json.loads(body) if body else {}


def _request_text(method: str, path: str) -> tuple[int, str]:
    url = f"{BASE_URL}{path}"
    req = request.Request(url, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8") if exc.fp else ""


def test_start_run() -> None:
    payload = {
        "repo_url": "https://example.com/repo.git",
        "start_prompt": "hello",
        "options": {
            "depth": 1,
            "include_evidence": False,
            "max_issues": 3,
            "enable_exec_probe": True,
        },
    }
    status, body = _request_json("POST", "/ingestion/runs", payload)
    assert status == 200
    assert isinstance(body.get("run_id"), str)
    assert isinstance(body.get("run_dir"), str)


def test_get_run() -> None:
    status, body = _request_json(
        "POST", "/ingestion/runs", {"repo_url": "https://example.com/repo.git"}
    )
    assert status == 200
    run_id = body["run_id"]
    status, body = _request_json("GET", f"/ingestion/runs/{run_id}")
    assert status == 200
    assert body.get("status") in {"PENDING", "RUNNING", "DONE", "FAILED"}
    assert "artifacts" in body
    assert "scopes" in body


def test_get_artifact_success() -> None:
    status, body = _request_json(
        "POST", "/ingestion/runs", {"repo_url": "https://example.com/repo.git"}
    )
    assert status == 200
    run_id = body["run_id"]
    status, text = _request_text(
        "GET", f"/ingestion/runs/{run_id}/artifacts/run_meta.json"
    )
    assert status == 200
    assert run_id in text


def test_get_artifact_not_found() -> None:
    status, body = _request_json(
        "POST", "/ingestion/runs", {"repo_url": "https://example.com/repo.git"}
    )
    assert status == 200
    run_id = body["run_id"]
    status, _text = _request_text("GET", f"/ingestion/runs/{run_id}/artifacts/missing")
    assert status == 404


if __name__ == "__main__":
    test_start_run()
    test_get_run()
    test_get_artifact_success()
    test_get_artifact_not_found()
    print("api_test.py: all tests passed")
