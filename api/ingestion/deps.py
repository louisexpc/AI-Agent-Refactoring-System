from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from shared.ingestion_types import ArtifactRef, RunRecord, RunStatus


class IngestionService(Protocol):
    """Ingestion 的服務介面定義。"""

    def start_run(
        self,
        repo_url: str,
        start_prompt: str | None,
        options: dict | None,
        save_path: str | None,
    ) -> tuple[str, str]: ...

    def run_pipeline(self, run_id: str) -> None: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def get_artifact(self, run_id: str, name: str) -> Path: ...

    def get_depgraph_filtered(self, run_id: str, lang: str, kind: str) -> Path: ...


class InMemoryIngestionService:
    """IngestionService 的 in-memory stub 實作。"""

    def __init__(self, artifacts_root: Path | None = None) -> None:
        """初始化 in-memory 儲存。

        Args:
            artifacts_root: artifacts 根目錄（可為 null，則使用預設路徑）。
        """
        self._runs: dict[str, RunRecord] = {}
        self._run_inputs: dict[
            str, tuple[str, str | None, dict | None, str | None, Path]
        ] = {}
        self._artifacts_root = artifacts_root

    def start_run(
        self,
        repo_url: str,
        start_prompt: str | None,
        options: dict | None,
        save_path: str | None,
    ) -> tuple[str, str]:
        """建立 run 並回傳 run_id。

        Args:
            repo_url: repo URL 或本機路徑。
            start_prompt: 啟動提示字串。
            options: 其他選項（dict）。

        Returns:
            (run_id, run_dir)。
        """
        from core.storage.artifacts import ArtifactLayout, default_artifacts_root
        from runner.ingestion_main import RunRepository, ensure_repo_root_on_path

        ensure_repo_root_on_path()
        repo_root = Path(__file__).resolve().parents[2]
        print(f"Repo root: {repo_root}")
        artifacts_root = self._artifacts_root or default_artifacts_root(repo_root)
        if save_path is not None:
            artifacts_root = normalize_save_path(save_path, base_dir=repo_root)
            print(f"Set artifacts_root to: {artifacts_root}")
        layout = ArtifactLayout(artifacts_root)
        repo = RunRepository(layout)
        run = repo.create_run(repo_url, start_prompt)
        run_id = run.run_id
        self._runs[run_id] = run
        self._run_inputs[run_id] = (
            repo_url,
            start_prompt,
            options,
            save_path,
            artifacts_root,
        )
        run_dir = layout.run_dir(run_id).resolve()
        return run_id, str(run_dir)

    def run_pipeline(self, run_id: str) -> None:
        """執行完整 ingestion pipeline。

        Args:
            run_id: run 識別碼。
        """
        from core.storage.artifacts import ArtifactLayout, default_artifacts_root
        from runner.data_assets import DbAssetIndexer, SqlInventoryExtractor
        from runner.depgraph import DepGraphExtractor
        from runner.evidence import GitHubEvidenceFetcher
        from runner.exec_matrix import ExecMatrixBuilder
        from runner.exec_probe import ExecProbeRunner
        from runner.indexer import RepoIndexer, ScopeClassifier
        from runner.ingestion_main import RunRepository, ensure_repo_root_on_path
        from runner.snapshot import Snapshotter

        ensure_repo_root_on_path()
        if run_id in self._run_inputs:
            (
                repo_url,
                start_prompt,
                _options,
                save_path,
                artifacts_root,
            ) = self._run_inputs[run_id]
        else:
            repo_url = None
            start_prompt = None
            _options = None
            repo_root = Path(__file__).resolve().parents[2]
            artifacts_root = self._artifacts_root or default_artifacts_root(repo_root)
        layout = ArtifactLayout(artifacts_root)
        repo = RunRepository(layout)

        run = repo.get_run(run_id)
        if repo_url is None:
            repo_url = run.repo_url
        if start_prompt is None:
            start_prompt = run.start_prompt
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
        repo_index_path.write_text(
            repo_index.model_dump_json(indent=2), encoding="utf-8"
        )
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
        exec_matrix_path.write_text(
            exec_matrix.model_dump_json(indent=2), encoding="utf-8"
        )

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
        dep_reverse_path.write_text(
            dep_reverse.model_dump_json(indent=2), encoding="utf-8"
        )
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
        dep_metrics_path.write_text(
            dep_metrics.model_dump_json(indent=2), encoding="utf-8"
        )
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

        evidence_fetcher = GitHubEvidenceFetcher(
            layout.run_dir(run.run_id) / "evidence"
        )
        evidence_index = evidence_fetcher.fetch(repo_url)
        evidence_index_path = (
            layout.run_dir(run.run_id) / "evidence" / "evidence_index.json"
        )
        evidence_index_path.write_text(
            evidence_index.model_dump_json(indent=2), encoding="utf-8"
        )
        artifacts = _collect_artifacts(layout.run_dir(run.run_id))
        run = run.model_copy(update={"artifacts": artifacts})
        repo._write_run(run)
        run = repo.update_status(run, RunStatus.DONE)
        self._runs[run_id] = run

    def get_run(self, run_id: str) -> RunRecord:
        """取得 run record。

        Args:
            run_id: run 識別碼。

        Returns:
            `RunRecord`。
        """
        from core.storage.artifacts import ArtifactLayout
        from runner.ingestion_main import RunRepository, ensure_repo_root_on_path

        ensure_repo_root_on_path()
        layout = ArtifactLayout(self._resolve_artifacts_root(run_id))
        repo = RunRepository(layout)
        return repo.get_run(run_id)

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
        from core.storage.artifacts import ArtifactLayout
        from runner.ingestion_main import ensure_repo_root_on_path

        ensure_repo_root_on_path()
        layout = ArtifactLayout(self._resolve_artifacts_root(run_id))
        run_dir = layout.run_dir(run_id)
        if not run_dir.exists():
            raise FileNotFoundError(f"artifact not available: {run_id}/{name}")

        candidates: list[Path] = []
        if "." in name:
            candidates.append(run_dir / name)
        else:
            candidates.append(run_dir / f"{name}.json")
            candidates.append(run_dir / name)
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.name == name or path.stem == name:
                return path
        raise FileNotFoundError(f"artifact not available: {run_id}/{name}")

    def get_depgraph_filtered(self, run_id: str, lang: str, kind: str) -> Path:
        """取得指定語言過濾後的 depgraph 相關檔案。

        Args:
            run_id: run 識別碼。
            lang: 目標語言（python/javascript/...）。
            kind: graph | metrics | reverse

        Returns:
            過濾後的檔案路徑。
        """
        from core.storage.artifacts import ArtifactLayout
        from runner.depgraph_filter import (
            SUPPORTED_LANGUAGES,
            filter_depgraph_json,
            filter_depmetrics_json,
            filter_depreverseindex_json,
        )

        if lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {lang}")
        if kind not in {"graph", "metrics", "reverse"}:
            raise ValueError(f"unsupported depgraph kind: {kind}")

        layout = ArtifactLayout(self._resolve_artifacts_root(run_id))
        run_dir = layout.run_dir(run_id)
        depgraph_dir = run_dir / "depgraph"
        if not depgraph_dir.exists():
            raise FileNotFoundError(f"depgraph dir not found: {run_id}")

        if kind == "graph":
            base = depgraph_dir / "dep_graph_light.json"
            if not base.exists():
                base = depgraph_dir / "dep_graph.json"
            if not base.exists():
                raise FileNotFoundError("dep_graph.json not found")
            return filter_depgraph_json(base, lang)

        if kind == "metrics":
            base = depgraph_dir / "dep_metrics.json"
            if not base.exists():
                raise FileNotFoundError("dep_metrics.json not found")
            return filter_depmetrics_json(base, lang)

        base = depgraph_dir / "dep_reverse_index_light.json"
        if not base.exists():
            base = depgraph_dir / "dep_reverse_index.json"
        if not base.exists():
            raise FileNotFoundError("dep_reverse_index.json not found")
        return filter_depreverseindex_json(base, lang)

    def _resolve_artifacts_root(self, run_id: str) -> Path:
        from core.storage.artifacts import default_artifacts_root

        repo_root = Path(__file__).resolve().parents[2]
        run_inputs = self._run_inputs.get(run_id)
        if run_inputs is not None:
            return run_inputs[4]
        return self._artifacts_root or default_artifacts_root(repo_root)


_service = InMemoryIngestionService()


def get_ingestion_service() -> IngestionService:
    """提供 ingestion service 依賴注入。"""
    return _service


def _collect_artifacts(run_dir: Path) -> dict[str, list[ArtifactRef]]:
    groups = {
        "depgraph": run_dir / "depgraph",
        "exec_matrix": run_dir / "exec",
        "index": run_dir / "index",
    }
    artifacts: dict[str, list[ArtifactRef]] = {}
    for key, base in groups.items():
        if not base.exists():
            continue
        entries: list[ArtifactRef] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            entries.append(
                ArtifactRef(
                    name=path.stem if path.suffix == ".json" else path.name,
                    path=str(path.resolve()),
                    sha256=_sha256_file(path),
                )
            )
        artifacts[key] = entries
    return artifacts


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def normalize_save_path(
    save_path: str | Path,
    *,
    base_dir: Path,
) -> Path:
    """Normalize save_path for artifacts output.

    Rules:
    - Absolute paths are used as-is (resolved).
    - Relative paths are anchored under base_dir.
    - Path traversal outside base_dir is rejected for relative paths.
    """
    p = Path(save_path)
    if p.is_absolute():
        return p.resolve()

    candidate = (base_dir / p).resolve()
    if not candidate.is_relative_to(base_dir):
        raise ValueError(f"Invalid save_path (escapes base_dir): {save_path}")
    return candidate
