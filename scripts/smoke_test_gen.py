"""Smoke test：用 LegacyCode 跑 test_gen pipeline。

用法：
    uv run python scripts/smoke_test_gen.py          # 無 LLM (stub)
    uv run python scripts/smoke_test_gen.py --llm    # 接 Vertex AI Gemini
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

# 確保 repo root 在 sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from runner.test_gen import run_module_test, run_overall_test  # noqa: E402
from shared.ingestion_types import (  # noqa: E402
    DepGraph,
    DepNode,
    RepoIndex,
)

# 忽略 Vertex AI SDK 的過期警告 (該功能將於 2026 年 6 月移除，目前可安全使用)
warnings.filterwarnings("ignore", message="This feature is deprecated")


def main() -> None:
    """用 LegacyCode 目錄模擬完整 test_gen pipeline。"""
    parser = argparse.ArgumentParser(description="Smoke test for test_gen pipeline")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="啟用 Vertex AI Gemini LLM（需要 GCP credentials）",
    )
    args = parser.parse_args()

    legacy_dir = repo_root / "LegacyCode"
    artifacts_root = repo_root / "artifacts"

    # 模擬上游 ingestion 產出的資料
    dep_graph = DepGraph(
        nodes=[
            DepNode(
                node_id="sensor.py",
                path="sensor.py",
                kind="file",
                lang="python",
                ext=".py",
            ),
            DepNode(
                node_id="tire_pressure_monitoring.py",
                path="tire_pressure_monitoring.py",
                kind="file",
                lang="python",
                ext=".py",
            ),
        ],
        edges=[],
    )

    repo_index = RepoIndex(
        root=".",
        file_count=3,
        total_bytes=800,
        files=[],
        indicators=["pytest"],
    )

    # LLM client
    llm_client = None
    if args.llm:
        from runner.test_gen.llm_adapter import create_vertex_client

        print("Initializing Vertex AI Gemini client...")
        llm_client = create_vertex_client()
        print("LLM client ready.\n")

    run_id = "smoke_legacy_llm" if args.llm else "smoke_legacy_test"

    # --- API 1: run_overall_test ---
    print("=" * 60)
    print("API 1: run_overall_test()")
    print("=" * 60)
    print(f"  repo_dir:   {legacy_dir}")
    print(f"  llm:        {'Vertex AI Gemini' if args.llm else 'None (stub)'}")
    print()

    overall_report = run_overall_test(
        run_id=run_id,
        repo_dir=legacy_dir,
        dep_graph=dep_graph,
        repo_index=repo_index,
        llm_client=llm_client,
        artifacts_root=artifacts_root,
        target_language="python",
    )

    print(f"Golden records: {len(overall_report.golden_snapshot.records)}")
    for rec in overall_report.golden_snapshot.records:
        status = "OK" if rec.exit_code == 0 else f"FAIL(exit={rec.exit_code})"
        output_str = str(rec.output)[:80] if rec.output else "(none)"
        print(f"  - {rec.file_path}: {status} -> {output_str}")
    print(f"Pass rate: {overall_report.pass_rate}")

    # --- API 2: run_module_test ---
    print()
    print("=" * 60)
    print("API 2: run_module_test()")
    print("=" * 60)

    module_report = run_module_test(
        run_id=run_id,
        repo_dir=legacy_dir,
        file_path="tire_pressure_monitoring.py",
        llm_client=llm_client,
        artifacts_root=artifacts_root,
        target_language="python",
    )

    print(f"  file_path: {module_report.file_path}")
    print(f"  can_test:  {module_report.can_test}")
    if module_report.emitted_file:
        print(f"  test_file: {module_report.emitted_file.path}")
        # 印前 10 行
        lines = module_report.emitted_file.content.split("\n")[:10]
        for line in lines:
            print(f"    {line}")
    if module_report.baseline_result:
        br = module_report.baseline_result
        print(
            f"  baseline:  total={br.total} passed={br.passed} "
            f"failed={br.failed} coverage={br.coverage_pct}"
        )
    print(f"  coverage:  {module_report.coverage_pct}")

    print()
    test_gen_dir = artifacts_root / run_id / "test_gen"
    print(f"Artifacts at: {test_gen_dir}")
    print("Done.")


if __name__ == "__main__":
    main()
