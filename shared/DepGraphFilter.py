from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def filter_depgraph_python_json(json_path: str | Path) -> Path:
    """
    Read a DepGraph JSON file, filter nodes/edges with lang == "python",
    and write a new JSON file whose name is suffixed with "_python".

    Example:
        input:  /repo/artifacts/dep_graph.json
        output: /repo/artifacts/dep_graph_python.json

    Returns:
        The output Path.
    """
    in_path = Path(json_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"JSON file not found: {in_path}")
    if in_path.suffix.lower() != ".json":
        raise ValueError(f"Expected a .json file, got: {in_path.name}")

    data: Dict[str, Any]
    with in_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Basic shape checks (lightweight, not full schema validation)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Invalid DepGraph JSON: 'nodes' and 'edges' must be lists.")

    def is_python_lang(v: Any) -> bool:
        return isinstance(v, str) and v.lower() == "python"

    filtered_nodes = [
        n for n in nodes if isinstance(n, dict) and is_python_lang(n.get("lang"))
    ]
    filtered_edges = [
        e for e in edges if isinstance(e, dict) and is_python_lang(e.get("lang"))
    ]

    # Keep all top-level fields, but replace nodes/edges with filtered versions
    out_data = dict(data)
    out_data["nodes"] = filtered_nodes
    out_data["edges"] = filtered_edges

    out_path = in_path.with_name(f"{in_path.stem}_python{in_path.suffix}")
    out_path.write_text(
        json.dumps(out_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def filter_depmetrics_python_json(json_path: str | Path) -> Path:
    """
    Read a DepMetrics JSON file, keep only DepFileMetrics entries whose `path`
    endswith ".py" (case-insensitive),
    and write a new JSON file suffixed with "_python".

    Example:
        input:  /repo/artifacts/dep_metrics.json
        output: /repo/artifacts/dep_metrics_python.json

    Returns:
        The output Path.
    """
    in_path = Path(json_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"JSON file not found: {in_path}")
    if in_path.suffix.lower() != ".json":
        raise ValueError(f"Expected a .json file, got: {in_path.name}")

    with in_path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    files = data.get("files", [])
    if not isinstance(files, list):
        raise ValueError("Invalid DepMetrics JSON: top-level 'files' must be a list.")

    def is_py_path(p: Any) -> bool:
        return isinstance(p, str) and p.lower().endswith(".py")

    filtered_files = [
        item
        for item in files
        if isinstance(item, dict) and is_py_path(item.get("path"))
    ]

    out_data = dict(data)
    out_data["files"] = filtered_files

    out_path = in_path.with_name(f"{in_path.stem}_python{in_path.suffix}")
    out_path.write_text(
        json.dumps(out_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def filter_depreverseindex_python_json(json_path: str | Path) -> Path:
    """
    Read a DepReverseIndex JSON file and keep DepReverseIndexEntry items where:
      - entry.dst endswith ".py" (case-insensitive), OR
      - any ref.src in entry.refs endswith ".py" (case-insensitive)

    Writes a new JSON file suffixed with "_python".

    Example:
        input:  /repo/artifacts/dep_reverse_index.json
        output: /repo/artifacts/dep_reverse_index_python.json

    Returns:
        The output Path.
    """
    in_path = Path(json_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"JSON file not found: {in_path}")
    if in_path.suffix.lower() != ".json":
        raise ValueError(f"Expected a .json file, got: {in_path.name}")

    with in_path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError(
            "Invalid DepReverseIndex JSON: top-level 'items' must be a list."
        )

    def is_py_path(p: Any) -> bool:
        return isinstance(p, str) and p.lower().endswith(".py")

    def keep_entry(entry: Any) -> bool:
        if not isinstance(entry, dict):
            return False

        # Rule 1: dst is .py
        if is_py_path(entry.get("dst")):
            return True

        # Rule 2: any ref.src is .py
        refs = entry.get("refs", [])
        if isinstance(refs, list):
            for r in refs:
                if isinstance(r, dict) and is_py_path(r.get("src")):
                    return True

        return False

    filtered_items = [e for e in items if keep_entry(e)]

    out_data = dict(data)
    out_data["items"] = filtered_items

    out_path = in_path.with_name(f"{in_path.stem}_python{in_path.suffix}")
    out_path.write_text(
        json.dumps(out_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


if __name__ == "__main__":
    root = (
        "/home/louisexpc/TSMC-2026-Hackathon/artifacts/2cca5c3ab95b491a9d42d7915c286bc6"
    )
    dep_graph_path = root + r"/depgraph/dep_graph_light.json"
    output_path = filter_depgraph_python_json(dep_graph_path)
    print(f"Filtered DepGraph JSON written to: {output_path}")
    metric_json_path = root + r"/depgraph/dep_metrics.json"
    output_metric_path = filter_depmetrics_python_json(metric_json_path)
    print(f"Filtered DepMetrics JSON written to: {output_metric_path}")

    dep_reverse_json_path = root + r"/depgraph/dep_reverse_index_light.json"
    output_depreverse_path = filter_depreverseindex_python_json(dep_reverse_json_path)
    print(f"Filtered DepReverseIndex JSON written to: {output_depreverse_path}")
