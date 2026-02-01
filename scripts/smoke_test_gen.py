"""Smoke test：用 LegacyCode 跑 test_gen pipeline。

用法：
    uv run python scripts/smoke_test_gen.py          # 無 LLM (stub)
    uv run python scripts/smoke_test_gen.py --llm    # 接 Vertex AI Gemini
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# 確保 repo root 在 sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from runner.test_gen import run_test_generation  # noqa: E402
from shared.ingestion_types import (  # noqa: E402
    DepEdge,
    DepGraphL0,
    DepNode,
    ExecMatrix,
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
    dep_graph = DepGraphL0(
        nodes=[
            DepNode(node_id="sensor.py", path="sensor.py", kind="file"),
            DepNode(
                node_id="tire_pressure_monitoring.py",
                path="tire_pressure_monitoring.py",
                kind="file",
            ),
        ],
        edges=[
            DepEdge(
                src="tire_pressure_monitoring.py",
                dst="sensor.py",
                kind="import",
                confidence=1.0,
            ),
        ],
    )

    repo_index = RepoIndex(
        root=".",
        file_count=3,
        total_bytes=800,
        files=[],
        indicators=["pytest"],
    )

    exec_matrix = ExecMatrix(scopes=[])

    # LLM client
    llm_client = None
    if args.llm:
        from runner.test_gen.llm_adapter import create_vertex_client

        print("Initializing Vertex AI Gemini client...")
        llm_client = create_vertex_client()
        print("LLM client ready.\n")

    run_id = "smoke_legacy_llm" if args.llm else "smoke_legacy_test"

    print("Running test_gen pipeline on LegacyCode...")
    print(f"  repo_dir:   {legacy_dir}")
    print(f"  llm:        {'Vertex AI Gemini' if args.llm else 'None (stub)'}")
    print(f"  artifacts:  {artifacts_root / run_id / 'test_gen'}")
    print()

    report = run_test_generation(
        run_id=run_id,
        repo_dir=legacy_dir,
        dep_graph=dep_graph,
        repo_index=repo_index,
        exec_matrix=exec_matrix,
        artifacts_root=artifacts_root,
        llm_client=llm_client,
        iteration=0,
    )

    # 印出結果
    test_gen_dir = artifacts_root / run_id / "test_gen"

    entries = json.loads((test_gen_dir / "entries.json").read_text())
    inputs_data = json.loads((test_gen_dir / "inputs.json").read_text())
    golden = json.loads((test_gen_dir / "golden_snapshot.json").read_text())
    guidance = json.loads((test_gen_dir / "guidance.json").read_text())

    print("=== Phase 1: Entry Detection ===")
    print(f"Entries detected: {len(entries['entries'])}")
    for e in entries["entries"]:
        print(f"  - {e['entry_id']} (sig: {e['signature']})")

    print("\n=== Phase 2: Guidance ===")
    for g in guidance["guidances"]:
        print(f"  - {g['module_path']}")
        if g["side_effects"]:
            print(f"    side_effects: {g['side_effects']}")
        if g["mock_recommendations"]:
            print(f"    mock: {g['mock_recommendations']}")
        if g["nondeterminism_notes"]:
            print(f"    nondeterminism: {g['nondeterminism_notes']}")

    print("\n=== Phase 3: Test Inputs ===")
    print(f"Inputs generated: {len(inputs_data['inputs'])}")
    for inp in inputs_data["inputs"]:
        print(f"  - {inp['entry_id']}: {inp['description']}")
        if inp["args"]:
            print(f"    args: {json.dumps(inp['args'])}")

    print("\n=== Phase 3b: Golden Capture ===")
    print(f"Golden records: {len(golden['records'])}")
    for rec in golden["records"]:
        status = "OK" if rec["exit_code"] == 0 else f"FAIL(exit={rec['exit_code']})"
        output_str = str(rec["output"])[:80] if rec["output"] else "(none)"
        print(f"  - {rec['entry_id']}: {status} -> {output_str}")

    # --- Generate Markdown Report ---
    md_lines = []
    md_lines.append(f"# Test Generation Report: {run_id}")
    md_lines.append(f"- **Date**: {run_id}")
    md_lines.append(f"- **LLM**: {'Vertex AI Gemini' if args.llm else 'None (stub)'}")
    md_lines.append(f"- **Target**: {legacy_dir.name}")
    md_lines.append("")

    md_lines.append("## Summary")
    md_lines.append("| Metric | Count |")
    md_lines.append("| :--- | :--- |")
    md_lines.append(f"| Total Tests | {report.total} |")
    md_lines.append(f"| Passed | {report.passed} |")
    md_lines.append(f"| Failed | {report.failed} |")
    md_lines.append(f"| Skipped | {report.skipped} |")
    md_lines.append("")

    md_lines.append("## Failure Details")
    if report.failed == 0:
        md_lines.append("🎉 No failures detected.")
    else:
        for rec in golden["records"]:
            if rec["exit_code"] != 0:
                md_lines.append(f"### ❌ {rec['entry_id']}")
                md_lines.append(f"- **Exit Code**: {rec['exit_code']}")
                md_lines.append("```text")
                md_lines.append(
                    str(rec["output"])[:500]
                    + ("..." if len(str(rec["output"])) > 500 else "")
                )
                md_lines.append("```")

    report_md_path = test_gen_dir / "report.md"
    report_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\n[Report] Markdown report generated at: {report_md_path}")
    # --------------------------------

    print("\n=== Phase 5: Emitted Test Files ===")
    print(f"Emitted files: {len(report.emitted_files)}")
    for ef in report.emitted_files:
        print(f"\n  --- {ef.path} ---")
        # 印前 20 行
        lines = ef.content.split("\n")[:20]
        for line in lines:
            print(f"    {line}")
        if len(ef.content.split("\n")) > 20:
            print(f"    ... ({len(ef.content.split(chr(10)))} lines total)")

    print("\n=== Report ===")
    print(
        f"total={report.total}, passed={report.passed}, "
        f"failed={report.failed}, skipped={report.skipped}"
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
