from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLayout:
    """定義 artifacts 目錄結構與固定路徑。

    Args:
        base_dir: artifacts 根目錄。
    """

    base_dir: Path

    def run_dir(self, run_id: str) -> Path:
        """取得 run 的根目錄路徑。

        Args:
            run_id: run 識別碼。

        Returns:
            run 目錄路徑。
        """
        return self.base_dir / run_id

    def run_meta_path(self, run_id: str) -> Path:
        """取得 run_meta.json 路徑。

        Args:
            run_id: run 識別碼。

        Returns:
            run_meta.json 的路徑。
        """
        return self.run_dir(run_id) / "run_meta.json"

    def ensure_run_layout(self, run_id: str) -> Path:
        """建立 run 需要的固定目錄骨架。

        Args:
            run_id: run 識別碼。

        Returns:
            run 目錄路徑。
        """
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        for subdir in (
            "snapshot",
            "index",
            "exec",
            "depgraph",
            "data",
            "evidence",
            "logs",
            "coverage",
        ):
            (run_dir / subdir).mkdir(parents=True, exist_ok=True)
        return run_dir


def default_artifacts_root(repo_root: Path) -> Path:
    """取得預設 artifacts 根目錄。

    Args:
        repo_root: repo root。

    Returns:
        artifacts 根目錄。
    """
    return repo_root / "artifacts"
