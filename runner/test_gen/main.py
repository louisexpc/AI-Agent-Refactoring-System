"""Generate Test 模組的 Orchestrator。

提供兩個公開 API：
- ``run_overall_test``: 建立 golden baseline / 執行 golden comparison。
- ``run_module_test``: 針對單一 module 生成 + 執行 unit test。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runner.test_gen.file_filter import FileFilter
from runner.test_gen.golden_capture import GoldenCaptureRunner
from runner.test_gen.golden_comparator import GoldenComparator
from runner.test_gen.guidance_gen import TestGuidanceGenerator
from runner.test_gen.output_normalizer import OutputNormalizer
from runner.test_gen.report_builder import ReportBuilder
from runner.test_gen.test_emitter import TestCodeEmitter
from runner.test_gen.test_runner import TestRunner
from shared.ingestion_types import DepGraph, RepoIndex
from shared.test_types import ModuleTestReport, OverallTestReport


def run_overall_test(
    run_id: str,
    repo_dir: Path,
    dep_graph: DepGraph,
    repo_index: RepoIndex,
    llm_client: Any = None,
    artifacts_root: Path = Path("artifacts"),
    target_language: str = "python",
    refactored_repo_dir: Path | None = None,
) -> OverallTestReport:
    """執行整體 golden test pipeline。

    iteration=0 時建立 golden baseline；
    有 refactored_repo_dir 時執行 golden comparison。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼（snapshot）的 repo 目錄。
        dep_graph: 依賴圖。
        repo_index: 檔案索引。
        llm_client: LLM 呼叫介面。
        artifacts_root: artifacts 根目錄。
        target_language: 目標語言。
        refactored_repo_dir: 重構後程式碼目錄（None 則只建 baseline）。

    Returns:
        OverallTestReport。
    """
    test_gen_dir = artifacts_root / run_id / "test_gen"
    test_gen_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = artifacts_root / run_id / "logs" / "test_gen"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: 過濾目標語言檔案
    file_filter = FileFilter(repo_dir=repo_dir)
    source_files = file_filter.filter(dep_graph, repo_index, target_language)
    _write_json(
        test_gen_dir / "source_files.json",
        {"files": [sf.model_dump() for sf in source_files]},
    )

    # Phase 2: LLM 生成測試指引
    guidance_gen = TestGuidanceGenerator(
        llm_client=llm_client, repo_dir=repo_dir, dep_graph=dep_graph
    )
    guidance_index = guidance_gen.build_for_files(source_files)
    _write_json(test_gen_dir / "guidance.json", guidance_index)

    # Phase 3: Golden Capture
    capture = GoldenCaptureRunner(
        repo_dir=repo_dir,
        logs_dir=logs_dir / "golden",
        llm_client=llm_client,
        dep_graph=dep_graph,
        guidance_index=guidance_index,
    )
    golden_snapshot = capture.run(source_files)
    _write_json(test_gen_dir / "golden_snapshot.json", golden_snapshot)

    # Golden Comparison（有重構後的 repo 時）
    comparison_results = []
    if refactored_repo_dir is not None:
        normalizer = OutputNormalizer()
        comparator = GoldenComparator(
            refactored_repo_dir=refactored_repo_dir,
            logs_dir=logs_dir,
            normalizer=normalizer,
        )
        comparison_results = comparator.run(source_files, golden_snapshot)

    # 建立報告
    builder = ReportBuilder()
    report = builder.build(
        run_id=run_id,
        golden_snapshot=golden_snapshot,
        comparison_results=comparison_results,
    )
    _write_json(test_gen_dir / "overall_report.json", report)

    return report


def run_module_test(
    run_id: str,
    repo_dir: Path,
    file_path: str,
    llm_client: Any = None,
    artifacts_root: Path = Path("artifacts"),
    target_language: str = "python",
    refactored_repo_dir: Path | None = None,
) -> ModuleTestReport:
    """針對單一 module 生成 + 執行 unit test。

    LLM 讀取來源檔案，判斷能否生成 unit test，
    能的話生成並執行，回傳結果。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼（snapshot）的 repo 目錄。
        file_path: 要測的檔案路徑（相對於 repo root）。
        llm_client: LLM 呼叫介面。
        artifacts_root: artifacts 根目錄。
        target_language: 目標語言。
        refactored_repo_dir: 重構後程式碼目錄。

    Returns:
        ModuleTestReport。
    """
    test_gen_dir = artifacts_root / run_id / "test_gen"
    emitted_dir = test_gen_dir / "emitted"
    emitted_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = artifacts_root / run_id / "logs" / "test_gen" / "unit_test"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 讀取來源檔案
    file_filter = FileFilter(repo_dir=repo_dir)
    source_file = file_filter.filter_single(file_path)

    if source_file is None:
        return ModuleTestReport(
            run_id=run_id,
            file_path=file_path,
            can_test=False,
        )

    # 生成 guidance
    guidance_gen = TestGuidanceGenerator(llm_client=llm_client, repo_dir=repo_dir)
    guidance = guidance_gen.build_for_single(source_file)

    # 生成 golden record（用舊 code 跑）
    golden_logs = artifacts_root / run_id / "logs" / "test_gen" / "module_golden"
    golden_logs.mkdir(parents=True, exist_ok=True)
    capture = GoldenCaptureRunner(
        repo_dir=repo_dir,
        logs_dir=golden_logs,
        llm_client=llm_client,
    )
    golden_snapshot = capture.run([source_file])
    golden_record = golden_snapshot.records[0] if golden_snapshot.records else None

    # 生成 unit test
    emitter = TestCodeEmitter(
        target_language=target_language,
        llm_client=llm_client,
        repo_dir=repo_dir,
    )
    emitted = emitter.emit_for_file(source_file, guidance, golden_record)

    # 寫入 emitted 測試檔
    emitted_path = emitted_dir / Path(emitted.path).name
    emitted_path.write_text(emitted.content, encoding="utf-8")

    # 跑 baseline（舊 code）
    baseline_result = None
    runner = TestRunner(
        repo_dir=repo_dir,
        test_dir=emitted_dir,
        logs_dir=logs_dir,
    )
    results = runner.run([emitted])
    if results:
        baseline_result = results[0]

    # 跑重構後 code（如有）
    refactored_result = None
    if refactored_repo_dir is not None:
        runner_ref = TestRunner(
            repo_dir=refactored_repo_dir,
            test_dir=emitted_dir,
            logs_dir=logs_dir,
        )
        ref_results = runner_ref.run([emitted])
        if ref_results:
            refactored_result = ref_results[0]

    # 取 coverage
    coverage_pct = None
    final_result = refactored_result or baseline_result
    if final_result and final_result.coverage_pct is not None:
        coverage_pct = final_result.coverage_pct

    report = ModuleTestReport(
        run_id=run_id,
        file_path=file_path,
        can_test=True,
        emitted_file=emitted,
        baseline_result=baseline_result,
        refactored_result=refactored_result,
        coverage_pct=coverage_pct,
    )

    _write_json(
        test_gen_dir / f"module_report_{Path(file_path).stem}.json",
        report,
    )

    return report


def _write_json(path: Path, model: Any) -> None:
    """將 Pydantic model 或 dict 序列化為 JSON 寫入檔案。

    Args:
        path: 輸出路徑。
        model: Pydantic BaseModel 實例或 dict。
    """
    import json

    if hasattr(model, "model_dump_json"):
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(model, indent=2, default=str), encoding="utf-8")
