from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import DepEdge, DepGraphL0, DepNode, RepoIndex

IMPORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("python", re.compile(r"^\s*import\s+([\w\.]+)|^\s*from\s+([\w\.]+)\s+import")),
    (
        "js",
        re.compile(
            r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(\s*['\"]([^'\"]+)['\"]\s*\)"
        ),
    ),
    ("go", re.compile(r"^\s*import\s+\(?\s*['\"]([^'\"]+)['\"]")),
    ("java", re.compile(r"^\s*import\s+([\w\.\*]+);")),
    ("c", re.compile(r"^\s*#include\s+[<\"]([^>\"]+)[>\"]")),
    ("rust", re.compile(r"^\s*use\s+([\w:]+)|^\s*mod\s+([\w_]+)")),
    ("php", re.compile(r"^\s*use\s+([\\\w]+)")),
    ("ruby", re.compile(r"^\s*require\s+['\"]([^'\"]+)['\"]")),
]


@dataclass
class DepGraphExtractor:
    repo_dir: Path

    def build(self, repo_index: RepoIndex) -> DepGraphL0:
        nodes: list[DepNode] = []
        edges: list[DepEdge] = []
        seen_edges: set[tuple[str, str]] = set()

        for entry in repo_index.files:
            node_id = entry.path
            nodes.append(DepNode(node_id=node_id, path=entry.path))
            file_path = self.repo_dir / entry.path
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in content.splitlines():
                for _lang, pattern in IMPORT_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    groups = [group for group in match.groups() if group]
                    for dst in groups:
                        edge_key = (node_id, dst)
                        if edge_key in seen_edges:
                            continue
                        seen_edges.add(edge_key)
                        edges.append(
                            DepEdge(src=node_id, dst=dst, kind="import", confidence=0.5)
                        )

        return DepGraphL0(nodes=nodes, edges=edges)
