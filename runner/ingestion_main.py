from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from core.storage.artifacts import ArtifactLayout
    from shared.ingestion_types import RunRecord, RunStatus


def ensure_repo_root_on_path() -> Path:
    """確保 repo root 已加入 sys.path。

    Returns:
        repo root 路徑。
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    return repo_root


@dataclass
class RunRepository:
    """Run metadata 的最小儲存介面。

    Args:
        layout: `ArtifactLayout` 實例。
    """

    layout: "ArtifactLayout"

    def create_run(self, repo_url: str, start_prompt: str | None) -> "RunRecord":
        """建立新的 run 並寫入 run_meta.json。

        Args:
            repo_url: repo URL 或本機路徑。
            start_prompt: 啟動提示字串。

        Returns:
            新建立的 `RunRecord`。
        """
        from shared.ingestion_types import RunRecord, RunStatus

        run_id = uuid4().hex
        now = datetime.now(tz=UTC)
        run = RunRecord(
            run_id=run_id,
            repo_url=repo_url,
            status=RunStatus.PENDING,
            commit_sha=None,
            start_prompt=start_prompt,
            created_at=now,
            updated_at=now,
        )
        self.layout.ensure_run_layout(run_id)
        self._write_run(run)
        return run

    def update_status(self, run: "RunRecord", status: "RunStatus") -> "RunRecord":
        """更新 run 狀態並落盤。

        Args:
            run: 既有的 `RunRecord`。
            status: 新狀態。

        Returns:
            更新後的 `RunRecord`。
        """
        now = datetime.now(tz=UTC)
        updated = run.model_copy(update={"status": status, "updated_at": now})
        self._write_run(updated)
        return updated

    def update_commit(self, run: "RunRecord", commit_sha: str) -> "RunRecord":
        """更新 commit SHA 並落盤。

        Args:
            run: 既有的 `RunRecord`。
            commit_sha: commit SHA。

        Returns:
            更新後的 `RunRecord`。
        """
        now = datetime.now(tz=UTC)
        updated = run.model_copy(update={"commit_sha": commit_sha, "updated_at": now})
        self._write_run(updated)
        return updated

    def get_run(self, run_id: str) -> "RunRecord":
        """讀取指定 run。

        Args:
            run_id: run 識別碼。

        Returns:
            `RunRecord`。
        """
        from shared.ingestion_types import RunRecord

        data = self.layout.run_meta_path(run_id).read_text(encoding="utf-8")
        return RunRecord.model_validate_json(data)

    def _write_run(self, run: "RunRecord") -> None:
        """寫入 run_meta.json。

        Args:
            run: 要寫入的 `RunRecord`。
        """
        path = self.layout.run_meta_path(run.run_id)
        path.write_text(run.model_dump_json(indent=2), encoding="utf-8")


def run_once(repo_url: str, start_prompt: str | None, artifacts_root: Path) -> str:
    """執行一次完整 ingestion pipeline。

    Args:
        repo_url: repo URL 或本機路徑。
        start_prompt: 啟動提示字串。
        artifacts_root: artifacts 根目錄。

    Returns:
        run_id。
    """
    ensure_repo_root_on_path()
    from core.storage.artifacts import ArtifactLayout
    from runner.data_assets import DbAssetIndexer, SqlInventoryExtractor
    from runner.depgraph import DepGraphExtractor
    from runner.evidence import GitHubEvidenceFetcher
    from runner.exec_matrix import ExecMatrixBuilder
    from runner.exec_probe import ExecProbeRunner
    from runner.indexer import RepoIndexer, ScopeClassifier
    from runner.snapshot import Snapshotter
    from shared.ingestion_types import RunStatus

    layout = ArtifactLayout(artifacts_root)
    repo = RunRepository(layout)
    run = repo.create_run(repo_url, start_prompt)
    run = repo.update_status(run, RunStatus.RUNNING)
    snapshotter = Snapshotter(work_dir=layout.run_dir(run.run_id) / "snapshot")
    snapshot_dir = layout.run_dir(run.run_id) / "snapshot" / "repo"
    snapshot_result = snapshotter.run(repo_url, snapshot_dir, create_archive=True)
    repo_meta_path = layout.run_dir(run.run_id) / "snapshot" / "repo_meta.json"
    repo_meta_path.write_text(
        snapshot_result.meta.model_dump_json(indent=2), encoding="utf-8"
    )
    run = repo.update_commit(run, snapshot_result.meta.commit_sha)

    indexer = RepoIndexer(snapshot_result.repo_dir)
    repo_index = indexer.build_index()
    repo_index_path = layout.run_dir(run.run_id) / "index" / "repo_index.json"
    repo_index_path.write_text(repo_index.model_dump_json(indent=2), encoding="utf-8")
    classifier = ScopeClassifier(snapshot_result.repo_dir)
    scopes = classifier.classify(repo_index)
    scope_path = layout.run_dir(run.run_id) / "index" / "scope_candidates.json"
    scope_payload = [scope.model_dump() for scope in scopes]
    scope_path.write_text(
        json.dumps(scope_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    run = run.model_copy(update={"scopes": scopes})
    repo._write_run(run)

    coverage_dir = layout.run_dir(run.run_id) / "coverage"
    exec_builder = ExecMatrixBuilder(coverage_dir=coverage_dir)
    exec_matrix = exec_builder.build(scopes)
    probe_runner = ExecProbeRunner(
        repo_dir=snapshot_result.repo_dir,
        logs_dir=layout.run_dir(run.run_id) / "logs" / "exec_probe",
        coverage_dir=coverage_dir,
    )
    try:
        exec_matrix = probe_runner.run(exec_matrix)
    except Exception:
        exec_matrix = exec_matrix
    exec_matrix_path = layout.run_dir(run.run_id) / "exec" / "exec_matrix.json"
    exec_matrix_path.write_text(exec_matrix.model_dump_json(indent=2), encoding="utf-8")

    depgraph = DepGraphExtractor(
        snapshot_result.repo_dir,
        logs_dir=layout.run_dir(run.run_id) / "logs",
    )
    dep_graph, dep_reverse, dep_metrics, external_inventory = depgraph.build_all(
        repo_index
    )
    dep_graph_path = layout.run_dir(run.run_id) / "depgraph" / "dep_graph.json"
    dep_graph_path.write_text(dep_graph.model_dump_json(indent=2), encoding="utf-8")
    dep_graph_light_path = (
        layout.run_dir(run.run_id) / "depgraph" / "dep_graph_light.json"
    )
    dep_graph_light_path.write_text(
        dep_graph.model_dump_json(
            indent=2,
            exclude={"edges": {"__all__": {"range", "symbol", "extras"}}},
        ),
        encoding="utf-8",
    )
    dep_reverse_path = (
        layout.run_dir(run.run_id) / "depgraph" / "dep_reverse_index.json"
    )
    dep_reverse_path.write_text(dep_reverse.model_dump_json(indent=2), encoding="utf-8")
    dep_reverse_light_path = (
        layout.run_dir(run.run_id) / "depgraph" / "dep_reverse_index_light.json"
    )
    dep_reverse_light_path.write_text(
        dep_reverse.model_dump_json(
            indent=2,
            exclude={"items": {"__all__": {"refs": {"__all__": {"range"}}}}},
        ),
        encoding="utf-8",
    )
    dep_metrics_path = layout.run_dir(run.run_id) / "depgraph" / "dep_metrics.json"
    dep_metrics_path.write_text(dep_metrics.model_dump_json(indent=2), encoding="utf-8")
    external_deps_path = (
        layout.run_dir(run.run_id) / "depgraph" / "external_deps_inventory.json"
    )
    external_deps_path.write_text(
        external_inventory.model_dump_json(indent=2), encoding="utf-8"
    )

    db_indexer = DbAssetIndexer(snapshot_result.repo_dir)
    db_assets = db_indexer.build(repo_index)
    db_assets_path = layout.run_dir(run.run_id) / "data" / "db_assets_index.json"
    db_assets_path.write_text(db_assets.model_dump_json(indent=2), encoding="utf-8")

    sql_extractor = SqlInventoryExtractor(snapshot_result.repo_dir)
    sql_inventory = sql_extractor.build(repo_index)
    sql_inventory_path = layout.run_dir(run.run_id) / "data" / "sql_inventory.json"
    sql_inventory_path.write_text(
        sql_inventory.model_dump_json(indent=2), encoding="utf-8"
    )

    evidence_fetcher = GitHubEvidenceFetcher(layout.run_dir(run.run_id) / "evidence")
    evidence_index = evidence_fetcher.fetch(repo_url)
    evidence_index_path = (
        layout.run_dir(run.run_id) / "evidence" / "evidence_index.json"
    )
    evidence_index_path.write_text(
        evidence_index.model_dump_json(indent=2), encoding="utf-8"
    )
    run = repo.update_status(run, RunStatus.DONE)
    return run.run_id


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。

    Returns:
        `ArgumentParser`。
    """
    parser = argparse.ArgumentParser(description="Run ingestion once")
    parser.add_argument("--repo_url", required=True)
    parser.add_argument("--start_prompt")
    parser.add_argument("--artifacts_root")
    return parser


def main() -> None:
    """CLI 入口點。"""
    parser = build_parser()
    args = parser.parse_args()
    repo_root = ensure_repo_root_on_path()
    from core.storage.artifacts import default_artifacts_root

    artifacts_root = (
        Path(args.artifacts_root)
        if args.artifacts_root
        else default_artifacts_root(repo_root)
    )
    run_id = run_once(args.repo_url, args.start_prompt, artifacts_root)
    print(run_id)
    return  # TODO: Artifact 路徑


if __name__ == "__main__":
    main()
