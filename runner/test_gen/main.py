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

from runner.test_gen.dep_resolver import resolve_dependency_context
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


# ---------------------------------------------------------------------------
# 5-Stage Pipeline Functions
# ---------------------------------------------------------------------------


def generate_stage1_golden(
    repo_dir: Path,
    before_files: list[str],
    dep_graph: DepGraph,
    llm_client: Any,
    test_result_dir: Path,
    source_language: str = "python",
    sandbox_base: str | None = None,
    local_base: Path | None = None,
) -> dict[str, Any]:
    """Stage 1: 生成 golden script + sh + requirements（不執行）。

    Args:
        repo_dir: 舊程式碼 repo 目錄。
        before_files: 舊檔案路徑清單。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        test_result_dir: 測試結果輸出目錄。
        source_language: 舊 code 語言。
        sandbox_base: Sandbox 內的基礎路徑（如 "/workspace"）。
        local_base: 對應 sandbox_base 的本地路徑（用於路徑轉換）。

    Returns:
        {
            "golden_dir": Path,
            "script_path": Path,
            "guidance": TestGuidance,
            "dep_signatures": dict,
        }
    """
    # 建立目錄
    golden_dir = test_result_dir / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)

    # 取得 plugin
    old_plugin = get_plugin(source_language)

    # 建立 SourceFile 物件
    old_sources = [SourceFile(path=p, lang=source_language) for p in before_files]

    # Phase 2: Guidance 生成
    logger.info("Generating test guidance for %s...", before_files)
    guidance_gen = TestGuidanceGenerator(
        llm_client=llm_client, repo_dir=repo_dir, dep_graph=dep_graph
    )
    guidance = guidance_gen.build_for_module(old_sources)

    # 寫出 guidance.json
    guidance_path = golden_dir / "guidance.json"
    guidance_path.write_text(
        json.dumps(guidance.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 收集 dep_signatures
    dep_signatures = {}
    for sf in old_sources:
        sig = resolve_dependency_context(dep_graph, sf.path, repo_dir)
        dep_signatures[sf.path] = sig
    dep_sigs_path = golden_dir / "dep_signatures_before.json"
    dep_sigs_path.write_text(
        json.dumps(dep_signatures, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 生成 golden script（用 LLM，不執行）
    logger.info("Generating golden script for %s...", before_files)
    source_code = _aggregate_source(old_sources, repo_dir)
    module_paths = [sf.path for sf in old_sources]

    golden_script = old_plugin.generate_golden_script(
        source_code=source_code,
        module_paths=module_paths,
        dep_signatures=dep_signatures,
        guidance=guidance.model_dump() if guidance else None,
        llm_client=llm_client,
    )

    # 寫入 golden script
    safe_name = before_files[0].replace("/", "_").replace(".", "_")
    if len(before_files) > 1:
        safe_name += "_module"
    script_path = golden_dir / f"{safe_name}_script.{_get_ext(source_language)}"
    script_path.write_text(golden_script, encoding="utf-8")

    # 生成執行文件（sh + requirements）
    old_source_dirs = list({str(Path(p).parent) for p in before_files})
    old_plugin.generate_execution_artifacts(
        repo_dir=repo_dir,
        output_dir=golden_dir,
        language=source_language,
        llm_client=llm_client,
        script_path=script_path,
        source_dirs=old_source_dirs,
        sandbox_base=sandbox_base,
        local_base=local_base,
    )

    logger.info("Stage 1 (golden) completed: %s", golden_dir)

    return {
        "golden_dir": golden_dir,
        "script_path": script_path,
        "guidance": guidance,
        "dep_signatures": dep_signatures,
    }


def generate_stage3_tests(
    refactored_repo_dir: Path,
    after_files: list[str],
    guidance: Any,  # TestGuidance
    dep_graph: DepGraph,
    llm_client: Any,
    test_result_dir: Path,
    target_language: str = "python",
    golden_records_path: Path | None = None,
    sandbox_base: str | None = None,
    local_base: Path | None = None,
) -> dict[str, Any]:
    """Stage 3: 讀取 golden_records，生成 test file + sh + requirements。

    Args:
        refactored_repo_dir: 重構後程式碼目錄。
        after_files: 新檔案路徑清單。
        guidance: Test guidance（從 Stage 1）。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        test_result_dir: 測試結果輸出目錄。
        target_language: 新 code 語言。
        golden_records_path: Golden records JSON 路徑（可選）。
        sandbox_base: Sandbox 內的基礎路徑（如 "/workspace"）。
        local_base: 對應 sandbox_base 的本地路徑（用於路徑轉換）。

    Returns:
        {
            "test_dir": Path,
            "test_file_path": Path,
            "dep_signatures": dict,
        }
    """
    # 建立目錄
    test_dir = test_result_dir / "test"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 取得 plugin
    new_plugin = get_plugin(target_language)

    # 建立 SourceFile 物件
    new_sources = [SourceFile(path=p, lang=target_language) for p in after_files]

    # 讀取 golden_records（如果提供）
    golden_records = []
    if golden_records_path and golden_records_path.exists():
        logger.info("Loading golden records from %s", golden_records_path)
        # 簡化版：直接當作 dict 使用，不用完整的 GoldenRecord 物件
        # 實際使用時 TestEmitter 會處理
        _ = json.loads(golden_records_path.read_text(encoding="utf-8"))
    else:
        logger.warning(
            "No golden records provided, generating test without golden anchoring"
        )

    # 收集 dep_signatures
    dep_signatures = {}
    for sf in new_sources:
        sig = resolve_dependency_context(dep_graph, sf.path, refactored_repo_dir)
        dep_signatures[sf.path] = sig
    dep_sigs_path = test_dir / "dep_signatures_after.json"
    dep_sigs_path.write_text(
        json.dumps(dep_signatures, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Phase 4: Test Emitter（生成測試，不執行）
    logger.info("Generating test file for %s...", after_files)
    emitter = ModuleTestEmitter(
        repo_dir=refactored_repo_dir,
        target_language=target_language,
    )

    # 如果有 golden_records，使用它們；否則傳空 list
    emitted = emitter.emit(
        after_files=new_sources,
        golden_records=golden_records,  # 會由 emitter 處理
        plugin=new_plugin,
        llm_client=llm_client,
        guidance=guidance,
        dep_graph=dep_graph,
    )

    # 寫入 test file
    emitted_path = test_dir / Path(emitted.path).name
    emitted_path.write_text(emitted.content, encoding="utf-8")

    # 計算 source_dirs
    source_dirs = list({str(Path(p).parent) for p in after_files})

    # 生成執行文件（sh + requirements）
    new_plugin.generate_execution_artifacts(
        repo_dir=refactored_repo_dir,
        output_dir=test_dir,
        language=target_language,
        llm_client=llm_client,
        test_file_path=emitted_path,
        source_dirs=source_dirs,
        sandbox_base=sandbox_base,
        local_base=local_base,
    )

    logger.info("Stage 3 (test) completed: %s", test_dir)

    return {
        "test_dir": test_dir,
        "test_file_path": emitted_path,
        "dep_signatures": dep_signatures,
    }


def generate_stage5_reports(
    run_id: str,
    repo_dir: Path,
    refactored_repo_dir: Path,
    records: list[CharacterizationRecord],
    llm_client: Any,
    test_result_dir: Path,
    target_language: str = "python",
) -> dict[str, Any]:
    """Stage 5: 生成最終報告（summary, test_records, review）。

    Args:
        run_id: Run 識別碼。
        repo_dir: 舊程式碼 repo 目錄。
        refactored_repo_dir: 重構後程式碼目錄。
        records: CharacterizationRecord 清單。
        llm_client: LLM 呼叫介面。
        test_result_dir: 測試結果輸出目錄。
        target_language: 新 code 語言。

    Returns:
        {
            "summary_path": str,
            "test_records_path": str,
            "review_path": str,
        }
    """
    # Build check（用新語言 plugin）
    logger.info("Running build check...")
    new_plugin = get_plugin(target_language)
    build_ok, build_output = new_plugin.check_build(
        repo_dir=refactored_repo_dir, timeout=60
    )
    build_error = build_output if not build_ok else None
    logger.info("Build check: success=%s", build_ok)

    # 建立 in-memory 報告
    report = build_stage_report(
        run_id=run_id,
        records=records,
        build_success=build_ok,
        build_error=build_error,
    )

    # 寫入三個輸出檔案到 test_result/
    test_result_dir.mkdir(parents=True, exist_ok=True)

    # 1. summary.json（統計）
    summary = build_summary(report)
    summary_path = test_result_dir / "summary.json"
    _write_json(summary_path, summary)

    # 2. test_records.json（事實）
    test_records = build_test_records(run_id=run_id, records=records)
    test_records_path = test_result_dir / "test_records.json"
    _write_json(test_records_path, test_records)

    # 3. review.json（LLM 分析）
    logger.info("Generating review with LLM...")
    reviewer = ReviewGenerator(
        llm_client=llm_client,
        repo_dir=repo_dir,
        refactored_repo_dir=refactored_repo_dir,
    )
    review = reviewer.generate_review(run_id=run_id, records=records)
    review_path = test_result_dir / "review.json"
    _write_json(review_path, review)

    logger.info("Stage 5 (reports) completed: %s", test_result_dir)

    return {
        "summary_path": str(summary_path),
        "test_records_path": str(test_records_path),
        "review_path": str(review_path),
    }


def run_characterization_test(
    run_id: str,
    repo_dir: Path,
    refactored_repo_dir: Path,
    before_files: list[str],
    after_files: list[str],
    dep_graph: DepGraph,
    llm_client: Any,
    workspace_root: Path = Path("workspace"),
    source_language: str = "python",
    target_language: str = "python",
    run_tests: bool = True,
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
        workspace_root: workspace 根目錄。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。
        run_tests: 是否執行測試（False = 只生成，不執行）。

    Returns:
        CharacterizationRecord。
    """
    # Stage 1 輸出結構：runs/<run_id>/stage1/{golden/, tests/}
    stage1_dir = workspace_root / "runs" / run_id / "stage1"
    golden_dir = stage1_dir / "golden"
    tests_dir = stage1_dir / "tests"
    for d in [golden_dir, tests_dir]:
        d.mkdir(parents=True, exist_ok=True)

    mapping = ModuleMapping(before_files=before_files, after_files=after_files)

    # 取得 plugins
    old_plugin = get_plugin(source_language)
    new_plugin = get_plugin(target_language)

    # 建立 SourceFile 物件
    old_sources = [SourceFile(path=p, lang=source_language) for p in before_files]
    new_sources = [SourceFile(path=p, lang=target_language) for p in after_files]

    # Phase 1.5: 檢查原始碼編譯（新 code）
    source_analysis = None
    after_file_paths = [refactored_repo_dir / p for p in after_files]
    logger.info("Checking source compilation for %s...", after_files)

    success, error_output = new_plugin.check_source_compilation(
        module_files=after_file_paths,
        work_dir=refactored_repo_dir,
    )

    if not success:
        logger.warning("Source compilation failed, analyzing with LLM...")
        source_analysis = new_plugin.analyze_source_with_llm(
            error_output=error_output,
            module_files=after_file_paths,
            language=target_language,
            llm_client=llm_client,
        )
        logger.info("Found %d source issues", len(source_analysis.issues))

        # 檢查是否有 safe_to_fix 的問題（未來可實作自動修復）
        safe_fixes = [
            issue
            for issue in source_analysis.issues
            if issue.severity.value == "safe_to_fix"
        ]
        if safe_fixes:
            logger.info(
                "Found %d safe-to-fix issues (not auto-fixing yet)",
                len(safe_fixes),
            )
    else:
        logger.info("Source compilation successful")

    # Phase 2: Guidance
    guidance_gen = TestGuidanceGenerator(
        llm_client=llm_client, repo_dir=repo_dir, dep_graph=dep_graph
    )
    guidance = guidance_gen.build_for_module(old_sources)

    # 寫出 guidance.json（debug 用）
    guidance_path = golden_dir / "guidance.json"
    guidance_path.write_text(
        json.dumps(guidance.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 收集並寫出 before_files 的 dep_signatures（debug 用）
    before_dep_sigs = {}
    for sf in old_sources:
        sig = resolve_dependency_context(dep_graph, sf.path, repo_dir)
        before_dep_sigs[sf.path] = sig
    before_dep_sigs_path = golden_dir / "dep_signatures_before.json"
    before_dep_sigs_path.write_text(
        json.dumps(before_dep_sigs, indent=2, ensure_ascii=False), encoding="utf-8"
    )

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

    # 寫出 golden_records.json（供 Docker 執行後讀取，或 debug 用）
    golden_records_path = golden_dir / "golden_records.json"
    golden_records_data = [gr.model_dump() for gr in golden_records]
    golden_records_path.write_text(
        json.dumps(golden_records_data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # 生成 golden script 的執行文件（requirements + sh）
    safe_name = before_files[0].replace("/", "_").replace(".", "_")
    if len(before_files) > 1:
        safe_name += "_module"
    golden_script_path = golden_dir / f"{safe_name}_script.py"
    old_source_dirs = list({str(Path(p).parent) for p in before_files})
    old_plugin.generate_execution_artifacts(
        repo_dir=repo_dir,
        output_dir=golden_dir,
        language=source_language,
        llm_client=llm_client,
        script_path=golden_script_path,
        source_dirs=old_source_dirs,
    )

    # 提取 tested_functions（golden output 的 keys）
    tested_functions: list[str] = []
    for gr in golden_records:
        if isinstance(gr.output, dict):
            tested_functions.extend(gr.output.keys())

    # 防呆：golden output 為空時警告
    golden_values_empty = all(
        not isinstance(gr.output, dict) or not gr.output for gr in golden_records
    )
    if golden_values_empty:
        logger.warning(
            "Golden capture produced no usable output for %s. "
            "Generated tests will lack golden anchoring and may not detect "
            "behavioral differences between old and new code.",
            before_files,
        )

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

    # 收集並寫出 after_files 的 dep_signatures（debug 用）
    after_dep_sigs = {}
    for sf in new_sources:
        sig = resolve_dependency_context(dep_graph, sf.path, refactored_repo_dir)
        after_dep_sigs[sf.path] = sig
    after_dep_sigs_path = tests_dir / "dep_signatures_after.json"
    after_dep_sigs_path.write_text(
        json.dumps(after_dep_sigs, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 計算 source_dirs：from file paths 取 unique 的 parent directories
    source_dirs = list({str(Path(p).parent) for p in after_files})

    # 生成 test file 的執行文件（requirements + sh）
    new_plugin.generate_execution_artifacts(
        repo_dir=refactored_repo_dir,
        output_dir=tests_dir,
        language=target_language,
        llm_client=llm_client,
        test_file_path=emitted_path,
        source_dirs=source_dirs,
    )

    # Phase 5: Test Runner（用新 code + 新語言 plugin）
    # 只在 run_tests=True 時執行
    test_result = None
    coverage_pct = None
    if run_tests:
        runner = ModuleTestRunner(
            work_dir=refactored_repo_dir,
            test_dir=tests_dir,
            logs_dir=tests_dir,  # log 也放 tests/
            source_dirs=source_dirs,
        )
        test_result = runner.run(test_file=emitted, plugin=new_plugin)
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
        source_analysis=source_analysis,
    )


def run_stage_test(
    run_id: str,
    repo_dir: Path,
    refactored_repo_dir: Path,
    stage_mappings: list[ModuleMapping],
    dep_graph: DepGraph,
    llm_client: Any,
    workspace_root: Path = Path("workspace"),
    source_language: str = "python",
    target_language: str = "python",
    run_tests: bool = True,
) -> StageTestReport:
    """整個 Stage 的測試，loop over mappings。

    Args:
        run_id: 所屬 run 的識別碼。
        repo_dir: 舊程式碼的 repo 目錄。
        refactored_repo_dir: 重構後程式碼目錄。
        stage_mappings: Stage Plan 的 module mappings。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        workspace_root: workspace 根目錄。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。
        run_tests: 是否執行測試（False = Stage 1 only，不執行測試）。

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
                workspace_root=workspace_root,
                source_language=source_language,
                target_language=target_language,
                run_tests=run_tests,
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

    # 寫入三個輸出檔案到 stage3/（分析階段）
    stage3_dir = workspace_root / "runs" / run_id / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)

    # 1. summary.json（統計）
    summary = build_summary(report)
    _write_json(stage3_dir / "summary.json", summary)

    # 2. test_records.json（事實）
    test_records = build_test_records(run_id=run_id, records=records)
    _write_json(stage3_dir / "test_records.json", test_records)

    # 3. review.json（LLM 分析）
    reviewer = ReviewGenerator(
        llm_client=llm_client,
        repo_dir=repo_dir,
        refactored_repo_dir=refactored_repo_dir,
    )
    review = reviewer.generate_review(run_id=run_id, records=records)
    _write_json(stage3_dir / "review.json", review)

    return report


def _write_json(path: Path, model: Any) -> None:
    """將 Pydantic model 或 dict 序列化為 JSON 寫入檔案。"""
    if hasattr(model, "model_dump_json"):
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(model, indent=2, default=str), encoding="utf-8")


def _aggregate_source(files: list[SourceFile], repo_dir: Path) -> str:
    """聚合多個檔案的原始碼，帶路徑標記。"""
    if len(files) == 1:
        return files[0].read_content(repo_dir)

    sections: list[str] = []
    for sf in files:
        content = sf.read_content(repo_dir)
        sections.append(
            f"File: {sf.path}\n"
            f"Directory: {str(Path(sf.path).parent)}\n"
            f"Module name: {Path(sf.path).stem}\n"
            f"```\n{content}\n```"
        )
    return "\n\n".join(sections)


def _get_ext(language: str) -> str:
    """根據語言取得檔案副檔名。"""
    ext_map = {
        "python": "py",
        "go": "go",
        "java": "java",
        "javascript": "js",
        "typescript": "ts",
    }
    return ext_map.get(language.lower(), "txt")
