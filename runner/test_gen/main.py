"""Generate Test 模組的 Orchestrator。

公開 API：
- ``run_stage_test``: 整個 Stage 的測試（外部入口）。

內部函式：
- ``run_characterization_test``: 單一 module mapping 的測試（由 run_stage_test 呼叫）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from runner.test_gen.golden_capture import ModuleGoldenCapture
from runner.test_gen.guidance_gen import TestGuidanceGenerator
from runner.test_gen.plugins import get_plugin
from runner.test_gen.report_builder import (
    build_stage_report,
    build_summary,
    build_test_records,
)
from runner.test_gen.review_gen import ReviewGenerator
from runner.test_gen.test_emitter import ModuleTestEmitter
from runner.test_gen.test_runner import ModuleTestRunner
from shared.ingestion_types import DepGraph
from shared.test_types import (
    CharacterizationRecord,
    ModuleMapping,
    SourceFile,
    StageTestReport,
)

logger = logging.getLogger(__name__)


def run_characterization_test(
    run_id: str,
    repo_dir: Path,
    refactored_repo_dir: Path,
    before_files: list[str],
    after_files: list[str],
    dep_graph: DepGraph,
    llm_client: Any,
    artifacts_root: Path = Path("artifacts"),
    source_language: str = "python",
    target_language: str = "python",
) -> CharacterizationRecord:
    """單一 module mapping 的 characterization test。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼的 repo 目錄。
        refactored_repo_dir: 重構後程式碼目錄。
        before_files: module 的舊檔案路徑清單。
        after_files: module 的新檔案路徑清單。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        artifacts_root: artifacts 根目錄。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。

    Returns:
        CharacterizationRecord。
    """
    # 新結構：golden/ 和 tests/ 攤平
    run_dir = artifacts_root / run_id
    golden_dir = run_dir / "golden"
    tests_dir = run_dir / "tests"
    for d in [golden_dir, tests_dir]:
        d.mkdir(parents=True, exist_ok=True)

    mapping = ModuleMapping(before_files=before_files, after_files=after_files)

    # 取得 plugins
    old_plugin = get_plugin(source_language)
    new_plugin = get_plugin(target_language)

    # 建立 SourceFile 物件
    old_sources = [SourceFile(path=p, lang=source_language) for p in before_files]
    new_sources = [SourceFile(path=p, lang=target_language) for p in after_files]

    # Phase 2: Guidance
    guidance_gen = TestGuidanceGenerator(
        llm_client=llm_client, repo_dir=repo_dir, dep_graph=dep_graph
    )
    guidance = guidance_gen.build_for_module(old_sources)

    # Phase 3: Golden Capture（用舊 code + 舊語言 plugin）
    capture = ModuleGoldenCapture(
        repo_dir=repo_dir,
        logs_dir=golden_dir,
    )
    golden_records = capture.run(
        before_files=old_sources,
        plugin=old_plugin,
        llm_client=llm_client,
        guidance=guidance,
        dep_graph=dep_graph,
    )

    # 提取 tested_functions（golden output 的 keys）
    tested_functions: list[str] = []
    for gr in golden_records:
        if isinstance(gr.output, dict):
            tested_functions.extend(gr.output.keys())

    # Phase 4: Test Emitter（用新 code + 新語言 plugin）
    emitter = ModuleTestEmitter(
        repo_dir=refactored_repo_dir,
        target_language=target_language,
    )
    emitted = emitter.emit(
        after_files=new_sources,
        golden_records=golden_records,
        plugin=new_plugin,
        llm_client=llm_client,
        guidance=guidance,
        dep_graph=dep_graph,
    )

    # 寫入 emitted 測試檔到 tests/
    emitted_path = tests_dir / Path(emitted.path).name
    emitted_path.write_text(emitted.content, encoding="utf-8")

    # Phase 5: Test Runner（用新 code + 新語言 plugin）
    runner = ModuleTestRunner(
        work_dir=refactored_repo_dir,
        test_dir=tests_dir,
        logs_dir=tests_dir,  # log 也放 tests/
    )
    test_result = runner.run(test_file=emitted, plugin=new_plugin)

    # 組裝 CharacterizationRecord
    coverage_pct = test_result.coverage_pct

    # 計算 golden_script_path（相對路徑）
    safe_name = before_files[0].replace("/", "_").replace(".", "_")
    if len(before_files) > 1:
        safe_name += "_module"
    golden_script_path = f"golden/{safe_name}_script.py"
    emitted_test_path = f"tests/{Path(emitted.path).name}"

    return CharacterizationRecord(
        module_mapping=mapping,
        golden_records=golden_records,
        emitted_test_file=emitted,
        test_result=test_result,
        coverage_pct=coverage_pct,
        tested_functions=tested_functions,
        golden_script_path=golden_script_path,
        emitted_test_path=emitted_test_path,
    )


def run_stage_test(
    run_id: str,
    repo_dir: Path,
    refactored_repo_dir: Path,
    stage_mappings: list[ModuleMapping],
    dep_graph: DepGraph,
    llm_client: Any,
    artifacts_root: Path = Path("artifacts"),
    source_language: str = "python",
    target_language: str = "python",
) -> StageTestReport:
    """整個 Stage 的測試，loop over mappings。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼的 repo 目錄。
        refactored_repo_dir: 重構後程式碼目錄。
        stage_mappings: Stage Plan 的 module mappings。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        artifacts_root: artifacts 根目錄。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。

    Returns:
        StageTestReport。
    """
    records: list[CharacterizationRecord] = []

    for mapping in stage_mappings:
        logger.info(
            "Running characterization test: %s -> %s",
            mapping.before_files,
            mapping.after_files,
        )
        try:
            record = run_characterization_test(
                run_id=run_id,
                repo_dir=repo_dir,
                refactored_repo_dir=refactored_repo_dir,
                before_files=mapping.before_files,
                after_files=mapping.after_files,
                dep_graph=dep_graph,
                llm_client=llm_client,
                artifacts_root=artifacts_root,
                source_language=source_language,
                target_language=target_language,
            )
            records.append(record)
        except Exception:
            logger.exception(
                "Failed characterization test for %s", mapping.before_files
            )
            records.append(CharacterizationRecord(module_mapping=mapping))

    # Build check（用新語言 plugin）
    new_plugin = get_plugin(target_language)
    build_ok, build_output = new_plugin.check_build(
        repo_dir=refactored_repo_dir, timeout=60
    )
    build_error = build_output if not build_ok else None
    logger.info("Build check: success=%s, output=%s", build_ok, build_output[:200])

    # 建立 in-memory 報告
    report = build_stage_report(
        run_id=run_id,
        records=records,
        build_success=build_ok,
        build_error=build_error,
    )

    # 寫入三個輸出檔案
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. summary.json（統計）
    summary = build_summary(report)
    _write_json(run_dir / "summary.json", summary)

    # 2. test_records.json（事實）
    test_records = build_test_records(run_id=run_id, records=records)
    _write_json(run_dir / "test_records.json", test_records)

    # 3. review.json（LLM 分析）
    reviewer = ReviewGenerator(
        llm_client=llm_client,
        repo_dir=repo_dir,
        refactored_repo_dir=refactored_repo_dir,
    )
    review = reviewer.generate_review(run_id=run_id, records=records)
    _write_json(run_dir / "review.json", review)

    return report


def _write_json(path: Path, model: Any) -> None:
    """將 Pydantic model 或 dict 序列化為 JSON 寫入檔案。"""
    if hasattr(model, "model_dump_json"):
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(model, indent=2, default=str), encoding="utf-8")
