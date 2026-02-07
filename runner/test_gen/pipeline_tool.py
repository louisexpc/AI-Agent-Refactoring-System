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

import re

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

_LOGGING_CONFIGURED = False


def _ensure_logging_configured() -> None:
    """確保 root logger 有基本配置，讓 runner.test_gen.* 的 log 能輸出。"""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    _LOGGING_CONFIGURED = True


# =========================
# LangGraph Tool
# =========================


@tool
def generate_test(
    mapping_path: str,
    use_sandbox: bool = False,
    sandbox_image: str = "refactor-sandbox:latest",
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
            (e.g. "workspace/stage_1/run_1/stage_plan/mapping_1_run_1.json").
        use_sandbox: Whether to execute scripts in Docker sandbox.
        sandbox_image: Docker image name for sandbox execution.

    Returns:
        JSON string: {"ok": bool, "test_result_dir": str,
            "summary_path": str, "test_records_path": str,
            "review_path": str, "error": str | null}
    """
    _ensure_logging_configured()

    try:
        from runner.test_gen.llm_adapter import create_vertex_client

        mapping_file = Path(mapping_path)
        if not mapping_file.exists():
            return json.dumps(
                {"ok": False, "error": f"Mapping file not found: {mapping_path}"},
                ensure_ascii=False,
            )

        mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
        
        # 驗證必要的字段
        required_fields = ["repo_dir", "refactored_repo_dir", "dep_graph_path", "mappings"]
        missing_fields = [f for f in required_fields if f not in mapping_data]
        if missing_fields:
            error_msg = (
                f"Mapping file missing required fields: {missing_fields}\n"
                f"Required schema: {{\n"
                f'  "repo_dir": "/workspace/init/<SHA256>/snapshot/repo",\n'
                f'  "refactored_repo_dir": "/workspace/refactor_repo",\n'
                f'  "dep_graph_path": "/workspace/init/<SHA256>/depgraph/dep_graph.json",\n'
                f'  "source_language": "python",\n'
                f'  "target_language": "go",\n'
                f'  "mappings": [{{"before": [...], "after": [...]}}]\n'
                f"}}"
            )
            return json.dumps(
                {"ok": False, "error": error_msg},
                ensure_ascii=False,
            )
        
        # 新結構：workspace/stage_X/run_I/stage_plan/mapping_X_run_I.json
        # test_result 與 stage_plan 平行，都在 run_I/ 下
        run_dir = mapping_file.parent.parent  # run_I/
        test_result_dir = str(run_dir / "test_result")
        # run_id 組合 stage 和 run index，例如 "stage_1_run_1"
        stage_dir = run_dir.parent  # stage_X/
        run_id = f"{stage_dir.name}_{run_dir.name}"  # e.g. "stage_1_run_1"
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
    sandbox_image: str = "refactor-sandbox:latest",
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
    _ensure_logging_configured()

    result_dir = Path(test_result_dir)
    repo = Path(repo_dir)
    refactored_repo = Path(refactored_repo_dir)

    # 載入 dep_graph
    logger.info("Loading dependency graph from %s", dep_graph_path)
    try:
        dep_graph_dict = json.loads(Path(dep_graph_path).read_text(encoding="utf-8"))
        
        # 防守性解析：自動修復常見缺失字段
        dep_graph = _parse_dep_graph_safely(dep_graph_dict)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from {dep_graph_path}: {e}"
        ) from e
    except Exception as e:
        # Pydantic ValidationError or other errors
        raise ValueError(
            f"Invalid dependency graph format.\n"
            f"Path: {dep_graph_path}\n"
            f"Error: {e}\n\n"
            f"Expected schema:\n"
            f"{{\n"
            f'  "nodes": [{{"node_id": "...", "path": "...", "lang": "...", "ext": "..."}}],\n'
            f'  "edges": [{{\n'
            f'    "src": "...",\n'
            f'    "lang": "python|ts|go|...",\n'
            f'    "ref_kind": "import|include|use|require|dynamic_import|other",\n'
            f'    "dst_raw": "...",\n'
            f'    "dst_norm": "...",\n'
            f'    "dst_kind": "internal_file|external_pkg|stdlib|relative|unknown",\n'
            f'    "range": {{"start_line": 1, "start_col": 0, "end_line": 1, "end_col": 10}},\n'
            f'    "confidence": 0.95\n'
            f'  }}],\n'
            f'  "version": "2",\n'
            f'  "generated_at": "2024-01-01T00:00:00Z" // optional\n'
            f"}}\n"
        ) from e

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
    emitted_test_file = stage3_result.get("emitted_test_file")

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

                # 解析 coverage
                coverage_pct = _parse_coverage_from_stdout(stdout, target_language)

                test_result = UnitTestResult(
                    test_file=str(test_file_path),
                    total=passed + failed + errored,
                    passed=passed,
                    failed=failed,
                    errored=errored,
                    coverage_pct=coverage_pct,
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
        emitted_test_file=emitted_test_file,
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


def _parse_dep_graph_safely(dep_graph_dict: dict) -> DepGraph:
    """防守性解析 DepGraph，自動修復常見缺失字段。

    此函數會自動處理：
    1. 缺失的 DepNode 或 DepEdge 字段（填入默認值）
    2. 缺失的 range 對象（填入默認 DepRange）
    3. 枚舉值錯誤（自動轉換為正確的枚舉值）

    Args:
        dep_graph_dict: 從 JSON 解析的字典。

    Returns:
        完整的 DepGraph 對象。

    Raises:
        ValueError: 如果無法修復（例如缺少絕對必需的 src/node_id）。
    """
    from shared.ingestion_types import DepRange, DepRefKind, DepDstKind

    # 處理 nodes
    nodes = []
    for node in dep_graph_dict.get("nodes", []):
        try:
            # 驗證必需字段 node_id 和 path
            if "node_id" not in node or "path" not in node:
                logger.warning(
                    "Skipping node with missing node_id or path: %s", node
                )
                continue

            # 使用默認值補填缺失字段
            node_safe = {
                "node_id": node.get("node_id"),
                "path": node.get("path"),
                "kind": node.get("kind", "file"),
                "lang": node.get("lang"),
                "ext": node.get("ext"),
            }
            nodes.append(node_safe)
        except Exception as e:
            logger.warning("Failed to process node: %s, error: %s", node, e)

    # 處理 edges
    edges = []
    for edge in dep_graph_dict.get("edges", []):
        try:
            # 驗證必需字段 src（至少需要來源）
            if "src" not in edge:
                logger.warning("Skipping edge with missing src: %s", edge)
                continue

            # 安全地獲取 range 對象，如果缺失則使用默認值
            range_dict = edge.get("range")
            if isinstance(range_dict, dict):
                try:
                    range_obj = DepRange(**range_dict)
                except Exception:
                    # 如果 range 解析失敗，使用默認值
                    range_obj = DepRange(
                        start_line=0, start_col=0, end_line=0, end_col=0
                    )
            else:
                # 缺失 range，使用默認值
                range_obj = DepRange(start_line=0, start_col=0, end_line=0, end_col=0)

            # 安全地解析 ref_kind 枚舉值
            ref_kind_str = edge.get("ref_kind", "other")
            try:
                ref_kind = DepRefKind(ref_kind_str)
            except (ValueError, KeyError):
                # 無效的枚舉值，使用默認值
                logger.warning(
                    "Invalid ref_kind '%s' for edge %s, using 'other'",
                    ref_kind_str,
                    edge.get("src"),
                )
                ref_kind = DepRefKind.OTHER

            # 安全地解析 dst_kind 枚舉值
            dst_kind_str = edge.get("dst_kind", "unknown")
            try:
                dst_kind = DepDstKind(dst_kind_str)
            except (ValueError, KeyError):
                # 無效的枚舉值，使用默認值
                logger.warning(
                    "Invalid dst_kind '%s' for edge %s, using 'unknown'",
                    dst_kind_str,
                    edge.get("src"),
                )
                dst_kind = DepDstKind.UNKNOWN

            # 組裝修復後的 edge
            edge_safe = {
                "src": edge.get("src"),
                "lang": edge.get("lang", "unknown"),
                "ref_kind": ref_kind,
                "dst_raw": edge.get("dst_raw", ""),
                "dst_norm": edge.get("dst_norm", ""),
                "dst_kind": dst_kind,
                "range": range_obj,
                "confidence": float(edge.get("confidence", 0.0)),
                "dst_resolved_path": edge.get("dst_resolved_path"),
                "symbol": edge.get("symbol"),
                "is_relative": edge.get("is_relative"),
                "extras": edge.get("extras", {}),
            }
            edges.append(edge_safe)
        except Exception as e:
            logger.warning("Failed to process edge: %s, error: %s", edge, e)

    # 組裝最終的 DepGraph
    return DepGraph(
        nodes=nodes,
        edges=edges,
        version=dep_graph_dict.get("version", "2"),
        generated_at=dep_graph_dict.get("generated_at"),
    )


def _parse_coverage_from_stdout(stdout: str, language: str) -> float | None:
    """從測試輸出解析 coverage 百分比。

    Args:
        stdout: 測試的標準輸出。
        language: 目標語言 (go, python, rust, kotlin, etc.)。

    Returns:
        Coverage 百分比，或 None（解析失敗時）。
    """
    if not stdout:
        return None

    if language == "go":
        # Go: "coverage: 85.7% of statements"
        match = re.search(r"coverage:\s+([\d.]+)%", stdout)
        if match:
            return float(match.group(1))
    elif language == "python":
        # pytest-cov: "TOTAL ... 85%"  or "Coverage: 85.7%"
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
        if match:
            return float(match.group(1))
        match = re.search(r"[Cc]overage[:\s]+(\d+(?:\.\d+)?)%", stdout)
        if match:
            return float(match.group(1))
    elif language == "rust":
        # cargo-tarpaulin: "85.71% coverage, 120/140 lines covered"
        match = re.search(r"([\d.]+)%\s+coverage", stdout)
        if match:
            return float(match.group(1))
        # Alternative format: "Coverage: 85.7%"
        match = re.search(r"[Cc]overage[:\s]+([\d.]+)%", stdout)
        if match:
            return float(match.group(1))
    elif language == "kotlin":
        # JaCoCo via Gradle: "Total coverage: 85.7%" or from XML report
        match = re.search(r"[Tt]otal\s+[Cc]overage[:\s]+([\d.]+)%", stdout)
        if match:
            return float(match.group(1))
        # Gradle format: "Coverage: 85.7%"
        match = re.search(r"[Cc]overage[:\s]+([\d.]+)%", stdout)
        if match:
            return float(match.group(1))
        # Line coverage format: "Line coverage: 85.7%"
        match = re.search(r"[Ll]ine\s+[Cc]overage[:\s]+([\d.]+)%", stdout)
        if match:
            return float(match.group(1))

    return None


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
