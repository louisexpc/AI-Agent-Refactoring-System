"""測試完整的 5-Stage characterization testing pipeline。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from runner.test_gen.llm_adapter import create_vertex_client
from runner.test_gen.pipeline_tool import run_characterization_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """測試 pipeline（不使用 sandbox）。"""
    # 讀取 mapping（從新目錄結構）
    mapping_file = Path("workspace/stage_1/stage_plan/mapping_1.json")
    logger.info("Loading mapping from %s", mapping_file)
    mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))

    # 建立 LLM client
    llm_client = create_vertex_client()

    # 輸出到 stage_plan/test_result/
    test_result_dir = str(mapping_file.parent / "test_result")
    run_id = "stage_1"
    logger.info("\n=== Running 5-Stage Pipeline (use_sandbox=False) ===")
    logger.info("Output: %s", test_result_dir)

    result = run_characterization_pipeline(
        run_id=run_id,
        test_result_dir=test_result_dir,
        repo_dir=mapping_data["repo_dir"],
        refactored_repo_dir=mapping_data["refactored_repo_dir"],
        mappings=mapping_data["mappings"],
        dep_graph_path=mapping_data["dep_graph_path"],
        llm_client=llm_client,
        source_language=mapping_data["source_language"],
        target_language=mapping_data["target_language"],
        sandbox_image="hack-sandbox:latest",
        use_sandbox=False,  # 不使用 Docker，只生成檔案
    )

    # 顯示結果
    logger.info("\n=== Pipeline Completed ===")
    logger.info("Summary path: %s", result["summary_path"])
    logger.info("Test records path: %s", result["test_records_path"])
    logger.info("Review path: %s", result["review_path"])
    logger.info("Test result dir: %s", result["test_result_dir"])

    # 驗證生成的檔案
    result_dir = Path(result["test_result_dir"])
    logger.info("\n=== Verifying Generated Files ===")

    golden_dir = result_dir / "golden"
    test_dir = result_dir / "test"
    logs_dir = result_dir / "logs"

    logger.info("\nGolden directory:")
    if golden_dir.exists():
        for f in sorted(golden_dir.iterdir()):
            logger.info("  - %s (%d bytes)", f.name, f.stat().st_size)
    else:
        logger.warning("  Golden directory not found!")

    logger.info("\nTest directory:")
    if test_dir.exists():
        for f in sorted(test_dir.iterdir()):
            logger.info("  - %s (%d bytes)", f.name, f.stat().st_size)
    else:
        logger.warning("  Test directory not found!")

    logger.info("\nLogs directory:")
    if logs_dir.exists():
        for f in sorted(logs_dir.iterdir()):
            logger.info("  - %s (%d bytes)", f.name, f.stat().st_size)
    else:
        logger.info("  (No logs - sandbox not used)")

    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
