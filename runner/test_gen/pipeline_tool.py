"""5-Stage Characterization Testing Pipeline Tool。

整合 Stage 1-5 + Docker sandbox 執行的完整 pipeline。
可作為 LangChain/LangGraph tool 或獨立函數使用。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# Optional LangChain import（沒裝時 @tool 退化為 no-op）nj3i
try:
    from langchain_core.tools import tool
except ImportError:

    def tool(fn):  # type: ignore[misc]
        return fn


# Optional sandbox import (只在使用 Docker 時需要)
try:
    from orchestrator import sandbox

    SANDBOX_AVAILABLE = True
except ImportError:
    SANDBOX_AVAILABLE = False
    sandbox = None  # type: ignore

from runner.test_gen.main import (
    generate_stage1_golden,
    generate_stage3_tests,
    generate_stage5_reports,
)
from runner.test_gen.test_runner import (
    _parse_failure_reasons,
    _parse_pytest_verbose_items,
    _parse_test_summary,
)
from shared.ingestion_types import DepGraph
from shared.test_types import (
    CharacterizationRecord,
    GoldenRecord,
    ModuleMapping,
    UnitTestResult,
)

logger = logging.getLogger(__name__)


# =========================
# LangGraph Tool
# =========================


@tool
def generate_test(
    mapping_path: str,
    use_sandbox: bool = True,
    sandbox_image: str = "hack-sandbox:latest",
) -> str:
    """Runs the 5-stage characterization testing pipeline for a refactoring stage.

    Reads a mapping JSON file that specifies old/new code file mappings,
    generates golden scripts, test files, and reports.
    If use_sandbox is True, also executes scripts in Docker containers.

    The mapping JSON should contain:
    - repo_dir, refactored_repo_dir, dep_graph_path
    - source_language, target_language
    - mappings: list of {before: [...], after: [...]}

    Output is written to test_result/ directory next to the mapping file.

    Args:
        mapping_path: Path to the mapping JSON file
            (e.g. "workspace/stage_1/stage_plan/mapping_1.json").
        use_sandbox: Whether to execute scripts in Docker sandbox.
        sandbox_image: Docker image name for sandbox execution.

    Returns:
        JSON string: {"ok": bool, "test_result_dir": str,
            "summary_path": str, "test_records_path": str,
            "review_path": str, "error": str | null}
    """
    try:
        from runner.test_gen.llm_adapter import create_vertex_client

        mapping_file = Path(mapping_path)
        if not mapping_file.exists():
            return json.dumps(
                {"ok": False, "error": f"Mapping file not found: {mapping_path}"},
                ensure_ascii=False,
            )

        mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
        test_result_dir = str(mapping_file.parent / "test_result")
        run_id = mapping_file.parent.parent.name  # e.g. "stage_1"
        llm_client = create_vertex_client()

        result = run_characterization_pipeline(
            run_id=run_id,
            test_result_dir=test_result_dir,
            repo_dir=mapping_data["repo_dir"],
            refactored_repo_dir=mapping_data["refactored_repo_dir"],
            mappings=mapping_data["mappings"],
            dep_graph_path=mapping_data["dep_graph_path"],
            llm_client=llm_client,
            source_language=mapping_data.get("source_language", "python"),
            target_language=mapping_data.get("target_language", "python"),
            sandbox_image=sandbox_image,
            use_sandbox=use_sandbox,
        )

        return json.dumps({"ok": True, **result}, ensure_ascii=False)
    except Exception as exc:
        logger.exception("generate_test failed")
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


# =========================
# Core Pipeline Function
# =========================


def run_characterization_pipeline(
    run_id: str,
    test_result_dir: str,
    repo_dir: str,
    refactored_repo_dir: str,
    mappings: list[dict[str, list[str]]],
    dep_graph_path: str,
    llm_client: Any,
    source_language: str = "python",
    target_language: str = "python",
    sandbox_image: str = "hack-sandbox:latest",
    use_sandbox: bool = True,
) -> dict[str, Any]:
    """完整的 5-Stage characterization testing pipeline。

    Args:
        run_id: Run 識別碼。
        test_result_dir: 測試結果輸出目錄路徑。
        repo_dir: 舊程式碼 repo 目錄路徑。
        refactored_repo_dir: 重構後程式碼目錄路徑。
        mappings: Module mappings（before/after files）。
        dep_graph_path: Dependency graph JSON 路徑。
        llm_client: LLM 呼叫介面。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。
        sandbox_image: Docker image 名稱。
        use_sandbox: 是否使用 Docker sandbox（False = 只生成檔案）。

    Returns:
        {
            "summary_path": str,
            "test_records_path": str,
            "review_path": str,
            "test_result_dir": str,
        }
    """
    result_dir = Path(test_result_dir)
    repo = Path(repo_dir)
    refactored_repo = Path(refactored_repo_dir)

    # 載入 dep_graph
    logger.info("Loading dependency graph from %s", dep_graph_path)
    dep_graph_dict = json.loads(Path(dep_graph_path).read_text(encoding="utf-8"))
    dep_graph = DepGraph(**dep_graph_dict)

    # 轉換 mappings
    module_mappings = [
        ModuleMapping(before_files=m["before"], after_files=m["after"])
        for m in mappings
    ]

    # 處理所有 module mappings
    records: list[CharacterizationRecord] = []
    sandbox_id = None

    # 計算 sandbox 路徑映射（用於生成正確的 shell script 路徑）
    # 找到 repo 和 test_result_dir 的共同父目錄作為 local_base
    repo_parts = repo.resolve().parts
    result_parts = result_dir.resolve().parts
    common_parts = []
    for rp, tp in zip(repo_parts, result_parts):
        if rp == tp:
            common_parts.append(rp)
        else:
            break
    local_base = Path(*common_parts) if common_parts else repo.resolve().parent
    sandbox_base = "/workspace"
    logger.info(
        "Path mapping: local_base=%s, sandbox_base=%s", local_base, sandbox_base
    )

    try:
        # 如果使用 sandbox，創建一次並重複使用
        if use_sandbox:
            if not SANDBOX_AVAILABLE:
                raise RuntimeError(
                    "Sandbox not available. "
                    "Install langchain_core or set use_sandbox=False"
                )
            logger.info("Creating sandbox with image %s", sandbox_image)

            mount_root = str(local_base)
            logger.info("Mounting %s to %s", mount_root, sandbox_base)

            create_payload = json.loads(
                sandbox.create_sandbox(
                    image=sandbox_image,
                    binds=[f"{mount_root}:/workspace"],
                    workdir="/workspace",
                )
            )
            sandbox_id = create_payload["sandbox_id"]
            logger.info("Sandbox created: %s", sandbox_id)

        for mapping in module_mappings:
            logger.info(
                "Processing mapping: %s -> %s",
                mapping.before_files,
                mapping.after_files,
            )

            try:
                record = _process_single_mapping(
                    run_id=run_id,
                    repo=repo,
                    refactored_repo=refactored_repo,
                    mapping=mapping,
                    dep_graph=dep_graph,
                    llm_client=llm_client,
                    test_result_dir=result_dir,
                    source_language=source_language,
                    target_language=target_language,
                    sandbox_id=sandbox_id if use_sandbox else None,
                    sandbox_base=sandbox_base,
                    local_base=local_base,
                )
                records.append(record)
            except Exception:
                logger.exception(
                    "Failed to process mapping for %s", mapping.before_files
                )
                # 創建空 record
                records.append(CharacterizationRecord(module_mapping=mapping))

        # Stage 5: 生成報告
        logger.info("Stage 5: Generating reports...")
        report_paths = generate_stage5_reports(
            run_id=run_id,
            repo_dir=repo,
            refactored_repo_dir=refactored_repo,
            records=records,
            llm_client=llm_client,
            test_result_dir=result_dir,
            target_language=target_language,
        )

        return {
            **report_paths,
            "test_result_dir": str(result_dir),
        }

    finally:
        # 清理 sandbox
        if sandbox_id:
            logger.info("Removing sandbox %s", sandbox_id)
            sandbox.remove_sandbox(sandbox_id=sandbox_id)


def _process_single_mapping(
    run_id: str,
    repo: Path,
    refactored_repo: Path,
    mapping: ModuleMapping,
    dep_graph: DepGraph,
    llm_client: Any,
    test_result_dir: Path,
    source_language: str,
    target_language: str,
    sandbox_id: str | None,
    sandbox_base: str | None = None,
    local_base: Path | None = None,
) -> CharacterizationRecord:
    """處理單一 module mapping 的完整 pipeline。

    Args:
        run_id: Run 識別碼。
        repo: 舊程式碼 repo 目錄。
        refactored_repo: 重構後程式碼目錄。
        mapping: Module mapping。
        dep_graph: 依賴圖。
        llm_client: LLM 呼叫介面。
        test_result_dir: 測試結果輸出目錄。
        source_language: 舊 code 語言。
        target_language: 新 code 語言。
        sandbox_id: Sandbox ID（如果使用）。
        sandbox_base: Sandbox 內的基礎路徑（如 "/workspace"）。
        local_base: 對應 sandbox_base 的本地路徑（用於路徑轉換）。

    Returns:
        CharacterizationRecord。
    """
    # Stage 1: 生成 golden script + sh + requirements
    logger.info("Stage 1: Generating golden script...")
    stage1_result = generate_stage1_golden(
        repo_dir=repo,
        before_files=mapping.before_files,
        dep_graph=dep_graph,
        llm_client=llm_client,
        test_result_dir=test_result_dir,
        source_language=source_language,
        sandbox_base=sandbox_base,
        local_base=local_base,
    )

    golden_dir = stage1_result["golden_dir"]
    guidance = stage1_result["guidance"]

    # Stage 2: Docker 執行 golden script（如果使用 sandbox）
    golden_records: list[GoldenRecord] = []
    logs_dir = test_result_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    if sandbox_id:
        logger.info("Stage 2: Executing golden script in sandbox...")
        execute_sh = golden_dir / "execute_golden.sh"
        if execute_sh.exists():
            try:
                # 計算 sandbox 內的路徑
                if local_base and sandbox_base:
                    sh_rel = execute_sh.resolve().relative_to(local_base.resolve())
                    sh_sandbox_path = f"{sandbox_base}/{sh_rel}"
                else:
                    sh_sandbox_path = "/workspace/test_result/golden/execute_golden.sh"

                # 執行 golden script
                result = sandbox.execute_command_in_sandbox(
                    sandbox_id=sandbox_id,
                    command=f"bash {sh_sandbox_path}",
                    workdir="/workspace",
                )
                logger.info("Golden script execution completed")

                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                exit_code = result.get("exit_code")

                # 寫入 log
                golden_log_path = logs_dir / "golden_execution.log"
                log_content = f"Exit Code: {exit_code}\n\n"
                log_content += f"STDOUT:\n{stdout}\n\n"
                log_content += f"STDERR:\n{stderr}\n"
                golden_log_path.write_text(log_content, encoding="utf-8")
                logger.info("Golden execution log written to %s", golden_log_path)

                # 從 stdout 解析 golden output（最後一行應該是 JSON）
                golden_output = _parse_golden_output_from_stdout(stdout)
                if golden_output:
                    # 建立 GoldenRecord（整個 module 一筆）
                    golden_records.append(
                        GoldenRecord(
                            file_path=",".join(mapping.before_files),
                            output=golden_output,
                            exit_code=exit_code,
                            stderr_snippet=stderr[:500] if stderr else None,
                        )
                    )
                    logger.info("Parsed golden output with %d keys", len(golden_output))

                    # 寫入 golden_records.json（供 Stage 3 使用）
                    golden_records_path = golden_dir / "golden_records.json"
                    golden_records_path.write_text(
                        json.dumps(
                            [gr.model_dump() for gr in golden_records],
                            indent=2,
                            default=str,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                else:
                    logger.warning(
                        "Failed to parse golden output from stdout, "
                        "exit_code=%s, stderr=%s",
                        exit_code,
                        stderr[:200] if stderr else "none",
                    )

                # 寫入結構化 JSON（Stage 2 輸出）
                stage2_output_path = logs_dir / "golden_result.json"
                stage2_output = {
                    "exit_code": exit_code,
                    "golden_records_count": len(golden_records),
                    "golden_records": [gr.model_dump() for gr in golden_records],
                }
                stage2_output_path.write_text(
                    json.dumps(
                        stage2_output, indent=2, default=str, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                logger.info("Stage 2 result written to %s", stage2_output_path)
            except Exception:
                logger.exception("Failed to execute golden script in sandbox")
        else:
            logger.warning("execute_golden.sh not found, skipping Stage 2")
    else:
        logger.info("Skipping Stage 2 (no sandbox)")

    # Stage 3: 生成 test file + sh + requirements
    logger.info("Stage 3: Generating test file...")
    golden_records_path = golden_dir / "golden_records.json"
    stage3_result = generate_stage3_tests(
        refactored_repo_dir=refactored_repo,
        after_files=mapping.after_files,
        guidance=guidance,
        dep_graph=dep_graph,
        llm_client=llm_client,
        test_result_dir=test_result_dir,
        target_language=target_language,
        golden_records_path=golden_records_path
        if golden_records_path.exists()
        else None,
        sandbox_base=sandbox_base,
        local_base=local_base,
    )

    test_dir = stage3_result["test_dir"]
    test_file_path = stage3_result["test_file_path"]

    # Stage 4: Docker 執行 test（如果使用 sandbox）
    test_result: UnitTestResult | None = None
    if sandbox_id:
        logger.info("Stage 4: Executing tests in sandbox...")
        execute_sh = test_dir / "execute_test.sh"
        if execute_sh.exists():
            try:
                # 計算 sandbox 內的路徑
                if local_base and sandbox_base:
                    sh_rel = execute_sh.resolve().relative_to(local_base.resolve())
                    sh_sandbox_path = f"{sandbox_base}/{sh_rel}"
                else:
                    sh_sandbox_path = "/workspace/test_result/test/execute_test.sh"

                # 執行 test
                result = sandbox.execute_command_in_sandbox(
                    sandbox_id=sandbox_id,
                    command=f"bash {sh_sandbox_path}",
                    workdir="/workspace",
                )
                logger.info("Test execution completed")

                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                exit_code = result.get("exit_code")

                # 寫入 log
                test_log_path = logs_dir / "test_execution.log"
                log_content = f"Exit Code: {exit_code}\n\n"
                log_content += f"STDOUT:\n{stdout}\n\n"
                log_content += f"STDERR:\n{stderr}\n"
                test_log_path.write_text(log_content, encoding="utf-8")
                logger.info("Test execution log written to %s", test_log_path)

                # 解析測試結果
                passed, failed, errored = _parse_test_summary(stdout)
                failure_reasons = _parse_failure_reasons(stdout)
                test_items = _parse_pytest_verbose_items(stdout, failure_reasons)

                test_result = UnitTestResult(
                    test_file=str(test_file_path),
                    total=passed + failed + errored,
                    passed=passed,
                    failed=failed,
                    errored=errored,
                    coverage_pct=None,  # TODO: 從 coverage report 解析
                    stdout=stdout[-2000:] if stdout else None,
                    stderr=stderr[-1000:] if stderr else None,
                    exit_code=exit_code,
                    test_items=test_items,
                )
                logger.info(
                    "Test results: %d passed, %d failed, %d errored",
                    passed,
                    failed,
                    errored,
                )

                # 寫入結構化 JSON（Stage 4 輸出）
                stage4_output_path = logs_dir / "test_result.json"
                stage4_output_path.write_text(
                    test_result.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                logger.info("Stage 4 result written to %s", stage4_output_path)
            except Exception:
                logger.exception("Failed to execute tests in sandbox")
        else:
            logger.warning("execute_test.sh not found, skipping Stage 4")
    else:
        logger.info("Skipping Stage 4 (no sandbox)")

    # 提取 tested_functions（golden output 的 keys）
    tested_functions: list[str] = []
    for gr in golden_records:
        if isinstance(gr.output, dict):
            tested_functions.extend(gr.output.keys())

    # 建立 CharacterizationRecord
    return CharacterizationRecord(
        module_mapping=mapping,
        golden_records=golden_records,
        emitted_test_file=None,  # TODO: 從 stage3_result 取得
        test_result=test_result,
        coverage_pct=test_result.coverage_pct if test_result else None,
        tested_functions=tested_functions,
        golden_script_path=str(stage1_result["script_path"]),
        emitted_test_path=str(test_file_path),
        source_analysis=None,
    )


# =========================
# Helper Functions
# =========================


def _parse_golden_output_from_stdout(stdout: str) -> dict | None:
    """從 golden script 的 stdout 解析 JSON output。

    Golden script 應該在最後一行輸出 JSON dict。

    Args:
        stdout: golden script 的標準輸出。

    Returns:
        解析後的 dict，或 None（解析失敗時）。
    """
    stdout = stdout.strip()
    if not stdout:
        return None

    # 嘗試解析最後一行（預期格式）
    last_line = stdout.split("\n")[-1].strip()
    try:
        result = json.loads(last_line)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 回退：嘗試解析整個 stdout
    try:
        result = json.loads(stdout)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return None
