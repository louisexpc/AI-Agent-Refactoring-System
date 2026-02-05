from __future__ import annotations

import json
from pathlib import Path

from shared.ingestion_types import (
    DbAssetsIndex,
    DepGraph,
    DepMetrics,
    DepReverseIndex,
    EvidenceIndex,
    ExecMatrix,
    ExternalDepsInventory,
    RepoIndex,
    RepoMeta,
    RunRecord,
    ScopeCandidate,
    SqlInventory,
)


def main() -> None:
    """輸出 shared schema 的 JSON Schema 檔案。"""
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)

    models = {
        "RunRecord": RunRecord,
        "RepoMeta": RepoMeta,
        "RepoIndex": RepoIndex,
        "ScopeCandidate": ScopeCandidate,
        "ExecMatrix": ExecMatrix,
        "DepGraph": DepGraph,
        "DepReverseIndex": DepReverseIndex,
        "DepMetrics": DepMetrics,
        "ExternalDepsInventory": ExternalDepsInventory,
        "DbAssetsIndex": DbAssetsIndex,
        "SqlInventory": SqlInventory,
        "EvidenceIndex": EvidenceIndex,
    }

    for name, model in models.items():
        schema = model.model_json_schema()
        (output_dir / f"{name}.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
