"""測試 TextConverter mapping 的 Stage 1 生成（不執行測試）。

驗證 generate_execution_artifacts() 功能：
- golden_records.json
- execute_golden.sh / requirements.txt (golden)
- execute_test.sh / requirements.txt or go.mod (test)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from runner.test_gen import run_stage_test
from runner.test_gen.llm_adapter import create_vertex_client
from shared.ingestion_types import DepGraph
from shared.test_types import ModuleMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run Stage 1 generation for TextConverter mapping."""
    # 讀取 mapping
    mapping_file = Path("workspace/TextConverter.json")
    logger.info("Loading mapping from %s", mapping_file)
    mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))

    # 路徑
    repo_dir = Path(mapping_data["repo_dir"])
    refactored_repo_dir = Path(mapping_data["refactored_repo_dir"])
    dep_graph_path = Path(mapping_data["dep_graph_path"])
    source_language = mapping_data["source_language"]
    target_language = mapping_data["target_language"]

    # 載入 dep_graph
    logger.info("Loading dep_graph from %s", dep_graph_path)
    dep_graph_dict = json.loads(dep_graph_path.read_text(encoding="utf-8"))
    dep_graph = DepGraph(**dep_graph_dict)

    # 建立 module mappings
    stage_mappings = [
        ModuleMapping(before_files=m["before"], after_files=m["after"])
        for m in mapping_data["mappings"]
    ]

    # 建立 LLM client
    llm_client = create_vertex_client()

    # 執行 Stage 1（不執行測試）
    run_id = "textconverter_stage1_test"
    workspace_root = Path("workspace")
    logger.info("Running Stage 1 generation (run_tests=False) for %s", run_id)

    report = run_stage_test(
        run_id=run_id,
        repo_dir=repo_dir,
        refactored_repo_dir=refactored_repo_dir,
        stage_mappings=stage_mappings,
        dep_graph=dep_graph,
        llm_client=llm_client,
        workspace_root=workspace_root,
        source_language=source_language,
        target_language=target_language,
        run_tests=False,  # 只生成檔案，不執行測試
    )

    # 驗證生成的檔案
    stage1_dir = workspace_root / "runs" / run_id / "stage1"
    golden_dir = stage1_dir / "golden"
    tests_dir = stage1_dir / "tests"

    logger.info("\n=== 驗證 Stage 1 產出 ===")

    # 檢查 golden 目錄
    logger.info("\nGolden directory contents:")
    golden_files = [
        "golden_records.json",
        "requirements.txt",  # Python source
        "execute_golden.sh",
    ]
    for f in golden_files:
        fpath = golden_dir / f
        if fpath.exists():
            logger.info("  ✓ %s (size: %d bytes)", f, fpath.stat().st_size)
        else:
            logger.warning("  ✗ %s NOT FOUND", f)

    # 檢查 tests 目錄
    logger.info("\nTests directory contents:")
    test_files = [
        "go.mod",  # Go target
        "execute_test.sh",
    ]
    for f in test_files:
        fpath = tests_dir / f
        if fpath.exists():
            logger.info("  ✓ %s (size: %d bytes)", f, fpath.stat().st_size)
        else:
            logger.warning("  ✗ %s NOT FOUND", f)

    # 列出實際生成的所有檔案
    logger.info("\nAll generated files in stage1/:")
    for dirpath in [golden_dir, tests_dir]:
        if dirpath.exists():
            logger.info("  %s:", dirpath.relative_to(workspace_root))
            for fpath in sorted(dirpath.iterdir()):
                logger.info("    - %s", fpath.name)

    # 顯示 report 摘要
    logger.info("\n=== Report Summary ===")
    logger.info("Total modules: %d", len(report.records))
    logger.info("Build success: %s", report.build_success)

    logger.info("\n=== Stage 1 生成完成 ===")
    logger.info("輸出目錄: %s", stage1_dir)


if __name__ == "__main__":
    main()
