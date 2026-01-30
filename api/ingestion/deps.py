from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from shared.ingestion_types import RunRecord, RunStatus


class IngestionService(Protocol):
    """Ingestion 的服務介面定義。"""

    def start_run(
        self, repo_url: str, start_prompt: str | None, options: dict | None
    ) -> str: ...

    def run_pipeline(self, run_id: str) -> None: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def get_artifact(self, run_id: str, name: str) -> Path: ...


class InMemoryIngestionService:
    """IngestionService 的 in-memory stub 實作。"""

    def __init__(self) -> None:
        """初始化 in-memory 儲存。"""
        self._runs: dict[str, RunRecord] = {}

    def start_run(
        self, repo_url: str, start_prompt: str | None, options: dict | None
    ) -> str:
        """建立 run 並回傳 run_id。

        Args:
            repo_url: repo URL 或本機路徑。
            start_prompt: 啟動提示字串。
            options: 其他選項（dict）。

        Returns:
            run_id。
        """
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
        """更新 run 狀態為 RUNNING（stub）。

        Args:
            run_id: run 識別碼。
        """
        run = self._runs[run_id]
        now = datetime.now(tz=UTC)
        self._runs[run_id] = run.model_copy(
            update={"status": RunStatus.RUNNING, "updated_at": now}
        )

    def get_run(self, run_id: str) -> RunRecord:
        """取得 run record。

        Args:
            run_id: run 識別碼。

        Returns:
            `RunRecord`。
        """
        return self._runs[run_id]

    def get_artifact(self, run_id: str, name: str) -> Path:
        """取得 artifact 路徑（stub）。

        Args:
            run_id: run 識別碼。
            name: artifact 名稱。

        Returns:
            檔案路徑。

        Raises:
            FileNotFoundError: stub 未提供檔案。
        """
        raise FileNotFoundError(f"artifact not available: {run_id}/{name}")


_service = InMemoryIngestionService()


def get_ingestion_service() -> IngestionService:
    """提供 ingestion service 依賴注入。"""
    return _service
