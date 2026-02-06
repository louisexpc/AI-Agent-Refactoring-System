"""測試完整的 5-Stage characterization testing pipeline。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from runner.test_gen.llm_adapter import create_vertex_client
from runner.test_gen.pipeline_tool import run_characterization_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _auto_find_mapping(repo_root: Path) -> Path:
    """Auto-detect a mapping_*.json under workspace/ or spec/workspace/.

    新結構：workspace/stage_X/run_I/stage_plan/mapping_X_run_I.json
    """
    candidates: list[Path] = []

    # 新結構：workspace/stage_X/run_I/stage_plan/
    for base in (
        repo_root / "workspace",
        repo_root / "spec" / "workspace",
    ):
        if base.is_dir():
            # 搜索 stage_*/run_*/stage_plan/mapping_*.json
            candidates.extend(
                sorted(base.glob("stage_*/run_*/stage_plan/mapping_*.json"))
            )

    if not candidates:
        raise FileNotFoundError(
            "No mapping_*.json found under:\n"
            f"  - {repo_root / 'workspace/stage_*/run_*/stage_plan/'}\n"
            f"  - {repo_root / 'spec/workspace/stage_*/run_*/stage_plan/'}\n"
            "Please generate the stage plan first or pass --mapping <path>."
        )

    # but good enough for now). If you want, we can sort by mtime instead.
    return candidates[-1]


def main() -> None:
    """測試 pipeline（不使用 sandbox）。"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mapping",
        type=str,
        default=None,
        help="Path to mapping_*.json (relative to repo root or absolute).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    if args.mapping:
        mapping_path = Path(args.mapping)
        mapping_file = (
            mapping_path if mapping_path.is_absolute() else (repo_root / mapping_path)
        )
    else:
        mapping_file = _auto_find_mapping(repo_root)

    logger.info("Loading mapping from %s", mapping_file)
    mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))

    # 建立 LLM client
    llm_client = create_vertex_client()

    # 新結構：test_result 與 stage_plan 平行，都在 run_I/ 下
    run_dir = mapping_file.parent.parent  # run_I/
    test_result_dir = str(run_dir / "test_result")
    stage_dir = run_dir.parent  # stage_X/
    run_id = f"{stage_dir.name}_{run_dir.name}"  # e.g. "stage_1_run_1"
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
        sandbox_image="refactor-sandbox:latest",
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
