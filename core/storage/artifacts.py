from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLayout:
    base_dir: Path

    def run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

    def run_meta_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run_meta.json"

    def ensure_run_layout(self, run_id: str) -> Path:
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
    return repo_root / "artifacts"
