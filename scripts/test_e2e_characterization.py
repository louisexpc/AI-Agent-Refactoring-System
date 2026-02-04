"""端對端測試：讀取 mock_mapping.json + dep_graph.json 跑 characterization test。

用法：
    python -m scripts.test_e2e_characterization
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# 確保 project root 在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from runner.test_gen.llm_adapter import create_vertex_client  # noqa: E402
from runner.test_gen.main import run_stage_test  # noqa: E402
from shared.ingestion_types import DepGraph  # noqa: E402
from shared.test_types import ModuleMapping  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

RUN_ID = "test_result"
MAPPING_FILE = PROJECT_ROOT / "scripts/mock_mapping.json"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"


def load_mapping_config(mapping_file: Path) -> dict:
    """讀取 mapping 設定檔。"""
    with open(mapping_file, encoding="utf-8") as f:
        return json.load(f)


def load_dep_graph(dep_graph_path: Path, lang_filter: str | None = None) -> DepGraph:
    """讀取 dep_graph.json 並過濾語言。

    Args:
        dep_graph_path: dep_graph.json 路徑。
        lang_filter: 語言過濾（如 "python"），None 則不過濾。

    Returns:
        DepGraph。
    """
    with open(dep_graph_path, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if lang_filter:
        # 過濾 nodes
        filtered_nodes = [
            n
            for n in nodes
            if n.get("lang") == lang_filter
            or n.get("path", "").startswith(f"{lang_filter.capitalize()}/")
        ]
        # 過濾 edges（src 或 dst 是該語言）
        filtered_paths = {n.get("path") for n in filtered_nodes}
        filtered_edges = [
            e
            for e in edges
            if e.get("src") in filtered_paths or e.get("lang") == lang_filter
        ]
        nodes = filtered_nodes
        edges = filtered_edges

    return DepGraph(nodes=nodes, edges=edges)


def main() -> None:
    """執行端對端 stage test。"""
    if not MAPPING_FILE.exists():
        logger.error("Mapping file not found: %s", MAPPING_FILE)
        sys.exit(1)

    # 讀取 mapping 設定
    config = load_mapping_config(MAPPING_FILE)
    source_language = config.get("source_language", "python")
    target_language = config.get("target_language", "python")
    repo_dir = PROJECT_ROOT / config["repo_dir"]
    refactored_repo_dir = PROJECT_ROOT / config["refactored_repo_dir"]
    dep_graph_path = PROJECT_ROOT / config["dep_graph_path"]

    # 建立 ModuleMapping 清單
    mappings = [
        ModuleMapping(before_files=m["before"], after_files=m["after"])
        for m in config["mappings"]
    ]

    print("=" * 60)
    print("MODULE MAPPINGS (from mock_mapping.json)")
    print("=" * 60)
    for i, m in enumerate(mappings):
        print(f"  [{i}] {m.before_files} -> {m.after_files}")
    print(f"  Total: {len(mappings)} modules\n")

    # 讀取 DepGraph
    logger.info("Loading dep_graph from %s...", dep_graph_path)
    dep_graph = load_dep_graph(dep_graph_path, lang_filter=source_language)
    logger.info(
        "  Loaded %d nodes, %d edges", len(dep_graph.nodes), len(dep_graph.edges)
    )

    # 建立 LLM client
    logger.info("Creating LLM client (Gemini 2.5 Pro)...")
    llm_client = create_vertex_client()

    # 執行 stage test
    logger.info("Running stage test with %d module mappings...", len(mappings))
    report = run_stage_test(
        run_id=RUN_ID,
        repo_dir=repo_dir,
        refactored_repo_dir=refactored_repo_dir,
        stage_mappings=mappings,
        dep_graph=dep_graph,
        llm_client=llm_client,
        artifacts_root=ARTIFACTS_ROOT,
        source_language=source_language,
        target_language=target_language,
    )

    # 印出結果
    print("\n" + "=" * 60)
    print("STAGE TEST REPORT")
    print("=" * 60)
    print(f"  Run ID:           {report.run_id}")
    print(f"  Build Success:    {report.build_success}")
    if report.build_error:
        print(f"  Build Error:      {report.build_error[:200]}")
    print(f"  Overall Pass Rate: {report.overall_pass_rate:.2%}")
    print(f"  Overall Coverage:  {report.overall_coverage_pct}")
    print(f"  Records:           {len(report.records)}")

    for i, rec in enumerate(report.records):
        print(f"\n  --- Module [{i}] ---")
        print(f"  before: {rec.module_mapping.before_files}")
        print(f"  after:  {rec.module_mapping.after_files}")

        if rec.golden_records:
            gr = rec.golden_records[0]
            print(f"  Golden: exit_code={gr.exit_code}, coverage={gr.coverage_pct}")
            if isinstance(gr.output, dict):
                keys = list(gr.output.keys())[:5]
                print(f"    output keys: {keys}{'...' if len(gr.output) > 5 else ''}")
            elif gr.output:
                print(f"    output: {str(gr.output)[:150]}")
            if gr.stderr_snippet:
                print(f"    stderr: {gr.stderr_snippet[:150]}")

        if rec.test_result:
            tr = rec.test_result
            print(
                f"  Test: passed={tr.passed}, failed={tr.failed}, "
                f"errored={tr.errored}, coverage={tr.coverage_pct}"
            )
            if tr.test_items:
                for item in tr.test_items:
                    print(f"    - {item.test_name}: {item.status.value}")
        else:
            print("  Test: NOT RUN")

        print(f"  Coverage: {rec.coverage_pct}")

    print("\n" + "=" * 60)

    # 提示產出位置
    print("\nArtifacts written to:")
    print(f"  {ARTIFACTS_ROOT / RUN_ID / 'summary.json'}")
    print(f"  {ARTIFACTS_ROOT / RUN_ID / 'test_records.json'}")
    print(f"  {ARTIFACTS_ROOT / RUN_ID / 'review.json'}")
    print(f"  {ARTIFACTS_ROOT / RUN_ID / 'golden/'}")
    print(f"  {ARTIFACTS_ROOT / RUN_ID / 'tests/'}")


if __name__ == "__main__":
    main()
