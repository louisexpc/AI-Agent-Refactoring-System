from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from shared.ingestion_types import RunRecord, RunStatus


class IngestionService(Protocol):
    def start_run(
        self, repo_url: str, start_prompt: str | None, options: dict | None
    ) -> str: ...

    def run_pipeline(self, run_id: str) -> None: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def get_artifact(self, run_id: str, name: str) -> Path: ...


class InMemoryIngestionService:
    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def start_run(
        self, repo_url: str, start_prompt: str | None, options: dict | None
    ) -> str:
        run_id = uuid4().hex
        now = datetime.now(tz=UTC)
        self._runs[run_id] = RunRecord(
            run_id=run_id,
            repo_url=repo_url,
            status=RunStatus.PENDING,
            commit_sha=None,
            start_prompt=start_prompt,
            created_at=now,
            updated_at=now,
        )
        return run_id

    def run_pipeline(self, run_id: str) -> None:
        run = self._runs[run_id]
        now = datetime.now(tz=UTC)
        self._runs[run_id] = run.model_copy(
            update={"status": RunStatus.RUNNING, "updated_at": now}
        )

    def get_run(self, run_id: str) -> RunRecord:
        return self._runs[run_id]

    def get_artifact(self, run_id: str, name: str) -> Path:
        raise FileNotFoundError(f"artifact not available: {run_id}/{name}")


_service = InMemoryIngestionService()


def get_ingestion_service() -> IngestionService:
    return _service
