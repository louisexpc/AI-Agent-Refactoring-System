"""Generate Test 模組的 Orchestrator。

串接所有 phase，提供單一入口 ``run_test_generation``
供迭代 pipeline 呼叫。

產出 artifact 寫入 ``artifacts/<run_id>/test_gen/``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runner.test_gen.entry_detector import EntryDetector
from runner.test_gen.golden_capture import GoldenCaptureRunner
from runner.test_gen.golden_comparator import GoldenComparator
from runner.test_gen.guidance_gen import TestGuidanceGenerator
from runner.test_gen.input_gen import TestInputGenerator
from runner.test_gen.output_normalizer import OutputNormalizer
from runner.test_gen.report_builder import TestReportBuilder
from runner.test_gen.test_emitter import TestCodeEmitter
from runner.test_gen.test_runner import TestRunner
from shared.ingestion_types import DepGraphL0, ExecMatrix, RepoIndex
from shared.test_types import TestReport


def run_test_generation(
    run_id: str,
    repo_dir: Path,
    dep_graph: DepGraphL0,
    repo_index: RepoIndex,
    exec_matrix: ExecMatrix,
    artifacts_root: Path,
    llm_client: Any = None,
    iteration: int = 0,
    refactored_repo_dir: Path | None = None,
    target_language: str = "python",
) -> TestReport:
    """執行完整測試生成 pipeline。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼（snapshot）的 repo 目錄。
        dep_graph: L0 依賴圖。
        repo_index: 檔案索引。
        exec_matrix: 執行矩陣。
        artifacts_root: artifacts 根目錄。
        llm_client: LLM 呼叫介面，None 表示使用 stub。
        iteration: 迭代輪次（0 表示迭代前）。
        refactored_repo_dir: 重構後程式碼目錄（None 則跳過比較）。
        target_language: 目標語言（python、go、typescript）。

    Returns:
        TestReport。
    """
    test_gen_dir = artifacts_root / run_id / "test_gen"
    test_gen_dir.mkdir(parents=True, exist_ok=True)
    (test_gen_dir / "emitted").mkdir(parents=True, exist_ok=True)
    logs_dir = artifacts_root / run_id / "logs" / "test_gen"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: 識別 entry points
    detector = EntryDetector(repo_dir=repo_dir)
    entry_index = detector.build(dep_graph, repo_index)
    _write_json(test_gen_dir / "entries.json", entry_index)

    # Phase 2: LLM 生成測試指引
    guidance_gen = TestGuidanceGenerator(repo_dir=repo_dir, llm_client=llm_client)
    guidance_index = guidance_gen.build(dep_graph, repo_index)
    _write_json(test_gen_dir / "guidance.json", guidance_index)

    # Phase 3: LLM 生成測試輸入
    input_gen = TestInputGenerator(repo_dir=repo_dir, llm_client=llm_client)
    input_set = input_gen.build(entry_index.entries, guidance_index)
    _write_json(test_gen_dir / "inputs.json", input_set)

    # Phase 3b: 執行舊程式碼，捕獲 golden output
    capture = GoldenCaptureRunner(
        repo_dir=repo_dir,
        logs_dir=logs_dir / "golden",
        llm_client=llm_client,
        guidance_index=guidance_index,
    )
    golden_snapshot = capture.run(input_set.inputs)
    _write_json(test_gen_dir / "golden_snapshot.json", golden_snapshot)

    # Phase 4: 比較（若有重構後的 repo）目前沒東西可以比
    results = []
    if refactored_repo_dir is not None:
        normalizer = OutputNormalizer()
        comparator = GoldenComparator(
            refactored_repo_dir=refactored_repo_dir,
            logs_dir=logs_dir,
            normalizer=normalizer,
        )
        results = comparator.run(input_set.inputs, golden_snapshot)

    # Phase 5: 產出可執行測試檔
    emitter = TestCodeEmitter(
        target_language=target_language,
        llm_client=llm_client,
    )
    emitted_files = emitter.emit(input_set.inputs, golden_snapshot, guidance_index)

    # 寫入 emitted 測試檔
    for emitted in emitted_files:
        emitted_path = test_gen_dir / "emitted" / Path(emitted.path).name
        emitted_path.write_text(emitted.content, encoding="utf-8")

    # Phase 5b: 執行 emitted tests，收集 pass/fail + coverage
    test_target_dir = refactored_repo_dir if refactored_repo_dir else repo_dir
    runner = TestRunner(
        repo_dir=test_target_dir,
        test_dir=test_gen_dir / "emitted",
        logs_dir=logs_dir / "unit_test",
    )
    unit_test_results = runner.run(emitted_files)

    # 彙總 unit test coverage
    coverage_values = [
        r.coverage_pct for r in unit_test_results if r.coverage_pct is not None
    ]
    avg_coverage = (
        round(sum(coverage_values) / len(coverage_values), 2)
        if coverage_values
        else None
    )

    # Phase 6: 產生報告
    report_builder = TestReportBuilder()
    report = report_builder.build(
        run_id=run_id,
        iteration=iteration,
        results=results,
        emitted_files=emitted_files,
        coverage_pct=avg_coverage,
    )
    # 補上 unit test 結果
    report.unit_test_results = unit_test_results
    _write_json(test_gen_dir / "test_report.json", report)

    return report


def _write_json(path: Path, model: Any) -> None:
    """將 Pydantic model 序列化為 JSON 寫入檔案。

    Args:
        path: 輸出路徑。
        model: Pydantic BaseModel 實例。
    """
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
