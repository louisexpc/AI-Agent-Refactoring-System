from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shared.ingestion_types import (
    DepDstKind,
    DepEdge,
    DepFileMetrics,
    DepGraph,
    DepMetrics,
    DepNode,
    DepRange,
    DepRef,
    DepRefKind,
    DepReverseIndex,
    DepReverseIndexEntry,
    ExternalDepItem,
    ExternalDepsInventory,
    RepoIndex,
)

try:
    from tree_sitter import Parser
    from tree_sitter_languages import get_language
except ImportError:  # pragma: no cover
    Parser = None
    get_language = None


_PARSER_CACHE: dict[str, Parser | None] = {}
_LANG_ERROR_ONCE: set[str] = set()


LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
}

QUERY_BY_LANG = {
    "python": """
    (import_statement) @import
    (import_from_statement) @from_import
    """,
    "javascript": """
    (import_statement
      source: (string (string_fragment) @import_path))
    (call_expression
      function: (identifier) @call_name
      arguments: (arguments (string (string_fragment) @import_path)))
    (import_call
      arguments: (arguments (string (string_fragment) @import_path)))
    """,
    "typescript": """
    (import_statement
      source: (string (string_fragment) @import_path))
    (call_expression
      function: (identifier) @call_name
      arguments: (arguments (string (string_fragment) @import_path)))
    (import_call
      arguments: (arguments (string (string_fragment) @import_path)))
    """,
    "go": """
    (import_spec path: (interpreted_string_literal) @import_path)
    """,
    "java": """
    (import_declaration (scoped_identifier) @import_path)
    """,
    "rust": """
    (use_declaration (use_tree) @import_path)
    """,
    "c": """
    (preproc_include
      path: (string_literal) @import_path)
    (preproc_include
      path: (system_lib_string) @import_path)
    """,
    "cpp": """
    (preproc_include
      path: (string_literal) @import_path)
    (preproc_include
      path: (system_lib_string) @import_path)
    """,
}

IMPORT_RE = re.compile(r"^\s*import\s+(.+)$")
FROM_IMPORT_RE = re.compile(r"^\s*from\s+([\.\w]+)\s+import\s+(.+)$")


@dataclass
class RawEdge:
    src: str
    lang: str
    ref_kind: DepRefKind
    dst_raw: str
    range: DepRange
    symbol: str | None = None
    is_relative: bool | None = None
    extras: dict[str, object] | None = None
    confidence: float = 0.3


@dataclass
class DepGraphExtractor:
    """建置新版 dependency graph 與衍生索引。"""

    repo_dir: Path
    logs_dir: Path

    def build_all(
        self, repo_index: RepoIndex
    ) -> tuple[DepGraph, DepReverseIndex, DepMetrics, ExternalDepsInventory]:
        """建構 dep graph 與 reverse index/metrics/inventory。

        Args:
            repo_index: RepoIndexer 產出的索引資料。

        Returns:
            (dep_graph, reverse_index, metrics, external_inventory)
        """
        errors_path = self.logs_dir / "dep_graph" / "errors.jsonl"
        errors_path.parent.mkdir(parents=True, exist_ok=True)

        module_map = _build_python_module_map(repo_index)
        file_set = {entry.path for entry in repo_index.files}

        nodes: list[DepNode] = []
        edges: list[DepEdge] = []
        dedupe: set[tuple] = set()

        for entry in sorted(repo_index.files, key=lambda e: e.path):
            lang = _detect_language(entry.path)
            nodes.append(
                DepNode(
                    node_id=entry.path,
                    path=entry.path,
                    kind="file",
                    lang=lang,
                    ext=entry.ext,
                )
            )
            if not lang:
                continue
            raw_edges = self._extract_edges(entry.path, lang, errors_path)
            for raw_edge in raw_edges:
                dep_edge = _normalize_edge(raw_edge, module_map, file_set)
                key = (
                    dep_edge.src,
                    dep_edge.ref_kind,
                    dep_edge.dst_norm,
                    dep_edge.dst_resolved_path or "",
                    dep_edge.symbol or "",
                    dep_edge.range.start_line,
                    dep_edge.range.start_col,
                )
                if key in dedupe:
                    continue
                dedupe.add(key)
                edges.append(dep_edge)

        edges.sort(
            key=lambda e: (
                e.src,
                e.ref_kind.value,
                e.dst_norm,
                e.range.start_line,
                e.range.start_col,
            )
        )
        graph = DepGraph(
            nodes=nodes,
            edges=edges,
            version="2",
            generated_at=datetime.now(tz=UTC),
        )
        reverse_index = _build_reverse_index(edges)
        metrics = _build_metrics(nodes, edges)
        external_inventory = _build_external_inventory(edges)
        return graph, reverse_index, metrics, external_inventory

    def _extract_edges(
        self, rel_path: str, lang: str, errors_path: Path
    ) -> list[RawEdge]:
        """解析單一檔案並抽取 RawEdge。

        Args:
            rel_path: 檔案相對路徑。
            lang: 語言識別。
            errors_path: 解析錯誤輸出路徑。

        Returns:
            RawEdge 列表。
        """
        file_path = self.repo_dir / rel_path
        try:
            code = file_path.read_bytes()
        except OSError as exc:
            _write_error(errors_path, rel_path, lang, str(exc))
            return []

        if Parser is None or get_language is None:
            _write_error(errors_path, rel_path, lang, "tree-sitter not available")
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )

        parser = _build_parser(lang)
        if parser is None:
            if lang not in _LANG_ERROR_ONCE:
                _LANG_ERROR_ONCE.add(lang)
                _write_error(errors_path, rel_path, lang, "tree-sitter unsupported")
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )

        tree = parser.parse(code)
        query_text = QUERY_BY_LANG.get(lang)
        if not query_text:
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )

        try:
            query = parser.language.query(query_text)
        except Exception as exc:  # pragma: no cover
            _write_error(errors_path, rel_path, lang, f"query error: {exc}")
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )

        captures = query.captures(tree.root_node)
        if lang == "python":
            return _extract_python_edges(rel_path, code, captures)
        if lang in {"javascript", "typescript"}:
            return _extract_js_edges(rel_path, lang, code, captures)
        return _extract_generic_edges(rel_path, lang, code, captures)


def _detect_language(path: str) -> str | None:
    return LANG_BY_EXT.get(Path(path).suffix.lower())


def _build_parser(lang: str) -> Parser | None:
    if lang in _PARSER_CACHE:
        return _PARSER_CACHE[lang]
    try:
        parser = Parser()
        parser.language = get_language(lang)
        _PARSER_CACHE[lang] = parser
        return parser
    except Exception:
        _PARSER_CACHE[lang] = None
        return None


def _extract_python_edges(
    rel_path: str,
    code: bytes,
    captures: list[tuple[object, str]],
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    for node, name in captures:
        if name not in {"import", "from_import"}:
            continue
        node_text = text[node.start_byte : node.end_byte]
        if name == "import":
            match = IMPORT_RE.match(node_text)
            if not match:
                continue
            modules = [part.strip().split(" ")[0] for part in match.group(1).split(",")]
            for module in modules:
                raw_edges.append(
                    RawEdge(
                        src=rel_path,
                        lang="python",
                        ref_kind=DepRefKind.IMPORT,
                        dst_raw=module,
                        range=_to_range(node),
                        confidence=0.9,
                    )
                )
        if name == "from_import":
            match = FROM_IMPORT_RE.match(node_text)
            if not match:
                continue
            module = match.group(1)
            symbol = match.group(2).split(",")[0].strip().split(" ")[0]
            level = len(module) - len(module.lstrip("."))
            is_relative = level > 0
            extras = {"python_level": level} if is_relative else {}
            raw_edges.append(
                RawEdge(
                    src=rel_path,
                    lang="python",
                    ref_kind=DepRefKind.IMPORT,
                    dst_raw=module,
                    range=_to_range(node),
                    symbol=symbol if symbol != "*" else None,
                    is_relative=is_relative,
                    extras=extras,
                    confidence=0.9,
                )
            )
    return raw_edges


def _extract_js_edges(
    rel_path: str,
    lang: str,
    code: bytes,
    captures: list[tuple[object, str]],
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    for node, name in captures:
        if name == "call_name":
            continue
        dst_raw = text[node.start_byte : node.end_byte]
        dst_raw = dst_raw.strip().strip("\"'")
        if not dst_raw:
            continue
        line_text = _line_text(text, node.start_point[0])
        ref_kind = DepRefKind.IMPORT
        confidence = 0.9
        if "require(" in line_text:
            ref_kind = DepRefKind.REQUIRE
            confidence = 0.85
        elif "import(" in line_text:
            ref_kind = DepRefKind.DYNAMIC_IMPORT
            confidence = 0.6
        raw_edges.append(
            RawEdge(
                src=rel_path,
                lang=lang,
                ref_kind=ref_kind,
                dst_raw=dst_raw,
                range=_to_range(node),
                confidence=confidence,
            )
        )
    return raw_edges


def _extract_generic_edges(
    rel_path: str,
    lang: str,
    code: bytes,
    captures: list[tuple[object, str]],
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    ref_kind = DepRefKind.IMPORT
    if lang in {"c", "cpp"}:
        ref_kind = DepRefKind.INCLUDE
    if lang == "rust":
        ref_kind = DepRefKind.USE

    for node, _name in captures:
        dst_raw = text[node.start_byte : node.end_byte]
        dst_raw = dst_raw.strip().strip("\"'<> ")
        if not dst_raw:
            continue
        raw_edges.append(
            RawEdge(
                src=rel_path,
                lang=lang,
                ref_kind=ref_kind,
                dst_raw=dst_raw,
                range=_to_range(node),
                confidence=0.85,
            )
        )
    return raw_edges


def _regex_fallback(rel_path: str, lang: str, text: str) -> list[RawEdge]:
    raw_edges: list[RawEdge] = []
    if lang == "python":
        for idx, line in enumerate(text.splitlines(), start=1):
            match = IMPORT_RE.match(line)
            if match:
                modules = [
                    part.strip().split(" ")[0] for part in match.group(1).split(",")
                ]
                for module in modules:
                    raw_edges.append(
                        RawEdge(
                            src=rel_path,
                            lang="python",
                            ref_kind=DepRefKind.IMPORT,
                            dst_raw=module,
                            range=DepRange(
                                start_line=idx,
                                start_col=0,
                                end_line=idx,
                                end_col=len(line),
                            ),
                        )
                    )
            match = FROM_IMPORT_RE.match(line)
            if match:
                module = match.group(1)
                symbol = match.group(2).split(",")[0].strip().split(" ")[0]
                level = len(module) - len(module.lstrip("."))
                raw_edges.append(
                    RawEdge(
                        src=rel_path,
                        lang="python",
                        ref_kind=DepRefKind.IMPORT,
                        dst_raw=module,
                        range=DepRange(
                            start_line=idx,
                            start_col=0,
                            end_line=idx,
                            end_col=len(line),
                        ),
                        symbol=symbol if symbol != "*" else None,
                        is_relative=level > 0,
                        extras={"python_level": level} if level > 0 else {},
                    )
                )
        return raw_edges

    for idx, line in enumerate(text.splitlines(), start=1):
        if "import" not in line and "require" not in line:
            continue
        ref_kind = DepRefKind.IMPORT
        if "require(" in line:
            ref_kind = DepRefKind.REQUIRE
        elif "#include" in line:
            ref_kind = DepRefKind.INCLUDE
        raw_edges.append(
            RawEdge(
                src=rel_path,
                lang=lang,
                ref_kind=ref_kind,
                dst_raw=line.strip(),
                range=DepRange(
                    start_line=idx,
                    start_col=0,
                    end_line=idx,
                    end_col=len(line),
                ),
            )
        )
    return raw_edges


def _normalize_edge(
    raw: RawEdge,
    module_map: dict[str, str],
    file_set: set[str],
) -> DepEdge:
    dst_raw = raw.dst_raw
    dst_norm = dst_raw
    dst_kind = DepDstKind.UNKNOWN
    dst_resolved_path = None
    is_relative = raw.is_relative
    extras: dict[str, object] = dict(raw.extras or {})
    confidence = raw.confidence

    if raw.lang == "python":
        level = extras.get("python_level", 0) if isinstance(extras, dict) else 0
        if is_relative:
            module_name = dst_raw.lstrip(".")
            dst_norm = f"REL{level}:{module_name}" if module_name else f"REL{level}:"
            resolved = _resolve_python_relative(
                raw.src, module_name, int(level), module_map
            )
            if resolved:
                dst_kind = DepDstKind.INTERNAL_FILE
                dst_resolved_path = resolved
                confidence = min(1.0, confidence)
            else:
                dst_kind = DepDstKind.RELATIVE
                confidence = min(confidence, 0.5)
        else:
            dst_norm = dst_raw
            resolved = _resolve_python_absolute(dst_norm, raw.symbol, module_map)
            if resolved:
                dst_kind = DepDstKind.INTERNAL_FILE
                dst_resolved_path = resolved
                if raw.symbol and resolved.endswith("__init__.py"):
                    confidence = min(confidence, 0.7)
            else:
                dst_kind = DepDstKind.EXTERNAL_PKG
        return DepEdge(
            src=raw.src,
            lang="python",
            ref_kind=raw.ref_kind,
            dst_raw=dst_raw,
            dst_norm=dst_norm,
            dst_kind=dst_kind,
            range=raw.range,
            confidence=confidence,
            dst_resolved_path=dst_resolved_path,
            symbol=raw.symbol,
            is_relative=is_relative,
            extras=extras,
        )

    if raw.lang in {"javascript", "typescript"}:
        dst_norm = dst_raw
        if dst_raw.startswith("./") or dst_raw.startswith("../"):
            is_relative = True
            resolved = _resolve_js_relative(raw.src, dst_raw, file_set)
            if resolved:
                dst_kind = DepDstKind.INTERNAL_FILE
                dst_resolved_path = resolved
                confidence = min(confidence, 0.9)
            else:
                dst_kind = DepDstKind.RELATIVE
                confidence = min(confidence, 0.5)
        else:
            dst_kind = DepDstKind.EXTERNAL_PKG
        return DepEdge(
            src=raw.src,
            lang=raw.lang,
            ref_kind=raw.ref_kind,
            dst_raw=dst_raw,
            dst_norm=dst_norm,
            dst_kind=dst_kind,
            range=raw.range,
            confidence=confidence,
            dst_resolved_path=dst_resolved_path,
            symbol=raw.symbol,
            is_relative=is_relative,
            extras=extras,
        )

    return DepEdge(
        src=raw.src,
        lang=raw.lang,
        ref_kind=raw.ref_kind,
        dst_raw=dst_raw,
        dst_norm=dst_norm,
        dst_kind=dst_kind,
        range=raw.range,
        confidence=confidence,
        dst_resolved_path=dst_resolved_path,
        symbol=raw.symbol,
        is_relative=is_relative,
        extras=extras,
    )


def _resolve_python_absolute(
    module_name: str, symbol: str | None, module_map: dict[str, str]
) -> str | None:
    if symbol:
        combined = f"{module_name}.{symbol}"
        if combined in module_map:
            return module_map[combined]
    if module_name in module_map:
        return module_map[module_name]
    return None


def _resolve_python_relative(
    src_path: str, module_name: str, level: int, module_map: dict[str, str]
) -> str | None:
    src_module = src_path.replace("/", ".")
    if src_module.endswith(".py"):
        src_module = src_module[:-3]
    parts = src_module.split(".")[:-1]
    if level > len(parts):
        return None
    base = parts[: len(parts) - level]
    if module_name:
        base.append(module_name)
    candidate = ".".join(base)
    if candidate in module_map:
        return module_map[candidate]
    if module_name:
        parent = ".".join(base[:-1])
        return module_map.get(parent)
    return None


def _resolve_js_relative(src_path: str, dst_raw: str, file_set: set[str]) -> str | None:
    src_dir = Path(src_path).parent
    base = (src_dir / dst_raw).as_posix()
    candidates = [
        base,
        f"{base}.ts",
        f"{base}.tsx",
        f"{base}.js",
        f"{base}.jsx",
        f"{base}/index.ts",
        f"{base}/index.tsx",
        f"{base}/index.js",
        f"{base}/index.jsx",
    ]
    for candidate in candidates:
        if candidate in file_set:
            return candidate
    return None


def _build_python_module_map(repo_index: RepoIndex) -> dict[str, str]:
    module_map: dict[str, str] = {}
    for entry in repo_index.files:
        if entry.path.endswith(".py"):
            module = entry.path[:-3].replace("/", ".")
            module_map[module] = entry.path
            if entry.path.endswith("/__init__.py"):
                pkg = entry.path[:-12].replace("/", ".")
                if pkg:
                    module_map[pkg] = entry.path
    return module_map


def _build_reverse_index(edges: list[DepEdge]) -> DepReverseIndex:
    bucket: dict[str, list[DepRef]] = {}
    for edge in edges:
        key = edge.dst_resolved_path or edge.dst_norm
        bucket.setdefault(key, []).append(DepRef(src=edge.src, range=edge.range))
    items = [
        DepReverseIndexEntry(dst=dst, refs=refs) for dst, refs in sorted(bucket.items())
    ]
    return DepReverseIndex(items=items)


def _build_metrics(nodes: list[DepNode], edges: list[DepEdge]) -> DepMetrics:
    node_paths = [node.path for node in nodes]
    out_edges: dict[str, set[str]] = {path: set() for path in node_paths}
    in_edges: dict[str, set[str]] = {path: set() for path in node_paths}
    total_out: dict[str, int] = {path: 0 for path in node_paths}
    total_in: dict[str, int] = {path: 0 for path in node_paths}

    for edge in edges:
        total_out[edge.src] = total_out.get(edge.src, 0) + 1
        if edge.dst_resolved_path:
            total_in[edge.dst_resolved_path] = (
                total_in.get(edge.dst_resolved_path, 0) + 1
            )
        if edge.dst_kind != DepDstKind.INTERNAL_FILE or not edge.dst_resolved_path:
            continue
        out_edges.setdefault(edge.src, set()).add(edge.dst_resolved_path)
        in_edges.setdefault(edge.dst_resolved_path, set()).add(edge.src)

    scc_map = _tarjan_scc(out_edges)
    metrics: list[DepFileMetrics] = []
    for path in node_paths:
        fan_out = len(out_edges.get(path, set()))
        fan_in = len(in_edges.get(path, set()))
        scc_id = scc_map.get(path)
        in_cycle = False
        if scc_id is not None:
            in_cycle = sum(1 for node, sid in scc_map.items() if sid == scc_id) > 1
        total_edges = total_in.get(path, 0) + total_out.get(path, 0)
        internal_ratio = None
        if total_edges > 0:
            internal_ratio = (fan_in + fan_out) / total_edges
        metrics.append(
            DepFileMetrics(
                path=path,
                fan_in=fan_in,
                fan_out=fan_out,
                in_cycle=in_cycle,
                scc_id=scc_id,
                internal_ratio=internal_ratio,
            )
        )
    return DepMetrics(files=sorted(metrics, key=lambda m: m.path))


def _build_external_inventory(edges: list[DepEdge]) -> ExternalDepsInventory:
    counts: dict[str, int] = {}
    importers: dict[str, set[str]] = {}
    for edge in edges:
        if edge.dst_kind == DepDstKind.EXTERNAL_PKG:
            counts[edge.dst_norm] = counts.get(edge.dst_norm, 0) + 1
            importers.setdefault(edge.dst_norm, set()).add(edge.src)
    items = []
    for dst_norm, count in sorted(counts.items()):
        top_importers = sorted(importers.get(dst_norm, set()))[:10]
        items.append(
            ExternalDepItem(dst_norm=dst_norm, count=count, top_importers=top_importers)
        )
    return ExternalDepsInventory(items=items)


def _tarjan_scc(graph: dict[str, set[str]]) -> dict[str, int]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    scc_id = 0
    result: dict[str, int] = {}

    def strongconnect(node: str) -> None:
        nonlocal index, scc_id
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            while True:
                w = stack.pop()
                on_stack.discard(w)
                result[w] = scc_id
                if w == node:
                    break
            scc_id += 1

    for node in graph:
        if node not in indices:
            strongconnect(node)

    return result


def _write_error(path: Path, rel_path: str, lang: str, message: str) -> None:
    entry = {"path": rel_path, "lang": lang, "error": message}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _line_text(text: str, line_idx: int) -> str:
    lines = text.splitlines()
    if 0 <= line_idx < len(lines):
        return lines[line_idx]
    return ""


def _to_range(node: object) -> DepRange:
    start = node.start_point
    end = node.end_point
    return DepRange(
        start_line=start[0] + 1,
        start_col=start[1],
        end_line=end[0] + 1,
        end_col=end[1],
    )
