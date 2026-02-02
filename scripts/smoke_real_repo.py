"""Smoke test：用真實 Racing-Car-Katas repo 測試 test_gen pipeline。

用法：
    python scripts/smoke_real_repo.py          # 無 LLM (stub)
    python scripts/smoke_real_repo.py --llm    # 接 Vertex AI Gemini
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from runner.test_gen import run_overall_test  # noqa: E402
from runner.test_gen.llm_adapter import create_vertex_client  # noqa: E402
from shared.ingestion_types import DepGraph, RepoIndex  # noqa: E402

warnings.filterwarnings("ignore", message="This feature is deprecated")

RUN_ID = "f3f7dfdffa4940d185668190b7a28b05"


def main() -> None:
    """用 Racing-Car-Katas 真實資料跑 test_gen pipeline。"""
    parser = argparse.ArgumentParser(description="Real repo smoke test")
    parser.add_argument("--llm", action="store_true", help="啟用 Vertex AI Gemini")
    args = parser.parse_args()

    base = repo_root / "artifacts" / RUN_ID
    repo_dir = base / "snapshot" / "repo"
    dep_graph = DepGraph(**json.loads((base / "depgraph/dep_graph.json").read_text()))
    repo_index = RepoIndex(**json.loads((base / "index/repo_index.json").read_text()))

    llm_client = None
    if args.llm:
        print("Initializing Vertex AI Gemini client...")
        llm_client = create_vertex_client()
        print("LLM client ready.\n")

    # --- API 1: run_overall_test ---
    print("=" * 60)
    print("API 1: run_overall_test()")
    print("=" * 60)
    print(f"  repo_dir: {repo_dir}")
    print(f"  llm:      {'Vertex AI Gemini' if args.llm else 'None (stub)'}")
    print()

    overall = run_overall_test(
        run_id=RUN_ID,
        repo_dir=repo_dir,
        dep_graph=dep_graph,
        repo_index=repo_index,
        llm_client=llm_client,
        artifacts_root=repo_root / "artifacts",
        target_language="python",
    )

    print(f"Golden records: {len(overall.golden_snapshot.records)}")
    for r in overall.golden_snapshot.records:
        status = "OK" if r.exit_code == 0 else f"FAIL(exit={r.exit_code})"
        output_str = str(r.output)[:80] if r.output else "(none)"
        print(f"  {r.file_path}: {status} -> {output_str}")
    print(f"Pass rate: {overall.pass_rate}")

    print()
    print(f"Artifacts at: {repo_root / 'artifacts' / RUN_ID / 'test_gen'}")
    print("Done.")


if __name__ == "__main__":
    main()
