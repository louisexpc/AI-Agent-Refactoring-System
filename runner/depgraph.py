from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

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
    # tree-sitter 0.20/0.21 has API differences across platforms and packages.
    # We normalize capture tuples and keep best-effort behavior when parsing fails.
    from tree_sitter import Language, Parser, Query, QueryCursor
except ImportError:  # pragma: no cover
    Language = None
    Parser = None
    Query = None
    QueryCursor = None


_PARSER_CACHE: dict[str, Parser | None] = {}
_PARSER_ERROR: dict[str, str] = {}
_LANG_ERROR_ONCE: set[str] = set()
_TREE_SITTER_READY = False
_TREE_SITTER_ERROR = ""


LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".php": "php",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".yaml": "yaml",
    ".md": "markdown",
    ".txt": "plaintext",
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
        """,
    "typescript": """
        (import_statement
            source: (string (string_fragment) @import_path))
        (call_expression
            function: (identifier) @call_name
            arguments: (arguments (string (string_fragment) @import_path)))
        """,
    "go": """
    (import_spec path: (interpreted_string_literal) @import_path)
    """,
    "java": """
    (import_declaration (scoped_identifier) @import_path)
    """,
    "rust": """
    (use_declaration) @import_path
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
CSHARP_USING_RE = re.compile(r"^\s*using\s+(?:static\s+)?([^;]+);\s*$")
PHP_USE_RE = re.compile(r"^\s*use\s+([^;]+);\s*$")
PHP_INCLUDE_RE = re.compile(
    r"^\s*(include|include_once|require|require_once)\s*\(?\s*['\"]([^'\"]+)['\"]"
)


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

        source_roots = _candidate_source_roots(repo_index)
        module_map = _build_python_module_map(repo_index, source_roots)
        csharp_map = _build_csharp_module_map(repo_index, source_roots)
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
                dep_edge = _normalize_edge(
                    raw_edge, module_map, csharp_map, file_set, source_roots
                )
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

        if not _TREE_SITTER_READY:
            if "tree-sitter" not in _LANG_ERROR_ONCE:
                _LANG_ERROR_ONCE.add("tree-sitter")
                _write_error(errors_path, rel_path, lang, _TREE_SITTER_ERROR)
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )

        parser = _build_parser(lang)
        if parser is None:
            if lang not in _LANG_ERROR_ONCE:
                _LANG_ERROR_ONCE.add(lang)
                message = _PARSER_ERROR.get(lang, "tree-sitter unsupported")
                _write_error(errors_path, rel_path, lang, message)
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
            query = Query(parser.language, query_text)
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
        except Exception as exc:  # pragma: no cover
            _write_error(errors_path, rel_path, lang, f"query error: {exc}")
            return _regex_fallback(
                rel_path, lang, code.decode("utf-8", errors="ignore")
            )
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
        parser.language = _get_language(lang)
        _PARSER_CACHE[lang] = parser
        return parser
    except Exception as exc:
        _PARSER_ERROR[lang] = f"tree-sitter unsupported: {exc}"
        _PARSER_CACHE[lang] = None
        return None


def _get_language(lang: str):
    if lang == "python":
        from tree_sitter_python import language as python_language

        return Language(python_language())
    if lang == "javascript":
        from tree_sitter_javascript import language as javascript_language

        return Language(javascript_language())
    if lang == "typescript":
        try:
            from tree_sitter_typescript import language as typescript_language

            return Language(typescript_language())
        except Exception:
            from tree_sitter_typescript import (
                language_typescript as typescript_language,
            )

            return Language(typescript_language())
    if lang == "csharp":
        from tree_sitter_c_sharp import language as csharp_language

        return Language(csharp_language())
    if lang == "php":
        try:
            from tree_sitter_php import language as php_language

            return Language(php_language())
        except Exception:
            from tree_sitter_php import language_php as php_language

            return Language(php_language())
    if lang == "go":
        from tree_sitter_go import language as go_language

        return Language(go_language())
    if lang == "java":
        from tree_sitter_java import language as java_language

        return Language(java_language())
    if lang == "rust":
        from tree_sitter_rust import language as rust_language

        return Language(rust_language())
    if lang == "c":
        from tree_sitter_c import language as c_language

        return Language(c_language())
    if lang == "cpp":
        from tree_sitter_cpp import language as cpp_language

        return Language(cpp_language())
    raise ValueError(f"unsupported language: {lang}")


def _probe_tree_sitter() -> None:
    global _TREE_SITTER_READY, _TREE_SITTER_ERROR
    if Parser is None or Language is None or Query is None or QueryCursor is None:
        _TREE_SITTER_READY = False
        _TREE_SITTER_ERROR = "tree-sitter not available"
        return
    try:
        parser = Parser()
        parser.language = _get_language("python")
        _TREE_SITTER_READY = True
        _TREE_SITTER_ERROR = ""
    except Exception as exc:
        _TREE_SITTER_READY = False
        _TREE_SITTER_ERROR = f"tree-sitter unsupported: {exc}"


def _iter_captures(
    captures: object,
) -> list[tuple[object, str]]:
    """Normalize QueryCursor capture results across tree-sitter versions.

    Newer bindings may return dict[str, list[Node]] instead of list[tuple].
    """
    normalized: list[tuple[object, str]] = []
    if isinstance(captures, dict):
        for name, nodes in captures.items():
            for node in nodes:
                if hasattr(node, "start_byte"):
                    normalized.append((node, name))
        return normalized

    for capture in captures:  # type: ignore[assignment]
        try:
            if len(capture) < 2:
                continue
        except TypeError:
            continue
        first = capture[0]
        second = capture[1]
        if hasattr(first, "start_byte"):
            node = first
            name = second
        elif hasattr(second, "start_byte"):
            node = second
            name = first
        else:
            continue
        normalized.append((node, name))
    return normalized


def _extract_python_edges(
    rel_path: str,
    code: bytes,
    captures: object,
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    for node, name in _iter_captures(captures):
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
    captures: object,
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    for node, name in _iter_captures(captures):
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
    captures: object,
) -> list[RawEdge]:
    text = code.decode("utf-8", errors="ignore")
    raw_edges: list[RawEdge] = []
    ref_kind = DepRefKind.IMPORT
    if lang in {"c", "cpp"}:
        ref_kind = DepRefKind.INCLUDE
    if lang == "rust":
        ref_kind = DepRefKind.USE

    for node, _name in _iter_captures(captures):
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

    if lang == "csharp":
        for idx, line in enumerate(text.splitlines(), start=1):
            match = CSHARP_USING_RE.match(line)
            if not match:
                continue
            target = match.group(1).strip()
            if "=" in target:
                target = target.split("=", 1)[-1].strip()
            if not target:
                continue
            raw_edges.append(
                RawEdge(
                    src=rel_path,
                    lang=lang,
                    ref_kind=DepRefKind.IMPORT,
                    dst_raw=target,
                    range=DepRange(
                        start_line=idx,
                        start_col=0,
                        end_line=idx,
                        end_col=len(line),
                    ),
                )
            )
        return raw_edges

    if lang == "php":
        for idx, line in enumerate(text.splitlines(), start=1):
            use_match = PHP_USE_RE.match(line)
            if use_match:
                target = use_match.group(1).strip()
                if " as " in target.lower():
                    target = target.rsplit(" as ", 1)[0].strip()
                if target:
                    raw_edges.append(
                        RawEdge(
                            src=rel_path,
                            lang=lang,
                            ref_kind=DepRefKind.IMPORT,
                            dst_raw=target,
                            range=DepRange(
                                start_line=idx,
                                start_col=0,
                                end_line=idx,
                                end_col=len(line),
                            ),
                        )
                    )
                continue
            include_match = PHP_INCLUDE_RE.match(line)
            if include_match:
                target = include_match.group(2).strip()
                if not target:
                    continue
                raw_edges.append(
                    RawEdge(
                        src=rel_path,
                        lang=lang,
                        ref_kind=DepRefKind.REQUIRE,
                        dst_raw=target,
                        range=DepRange(
                            start_line=idx,
                            start_col=0,
                            end_line=idx,
                            end_col=len(line),
                        ),
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
    csharp_map: dict[str, str],
    file_set: set[str],
    source_roots: list[str],
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
                raw.src,
                module_name,
                int(level),
                module_map,
                file_set,
                raw.symbol,
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
        dst_kind, dst_resolved_path, confidence = _maybe_infer_internal(
            raw.src,
            dst_raw,
            dst_norm,
            file_set,
            dst_kind,
            dst_resolved_path,
            confidence,
        )
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
            resolved = _resolve_js_absolute(dst_raw, file_set, source_roots)
            if resolved:
                dst_kind = DepDstKind.INTERNAL_FILE
                dst_resolved_path = resolved
                confidence = min(confidence, 0.9)
            else:
                dst_kind = DepDstKind.EXTERNAL_PKG
        dst_kind, dst_resolved_path, confidence = _maybe_infer_internal(
            raw.src,
            dst_raw,
            dst_norm,
            file_set,
            dst_kind,
            dst_resolved_path,
            confidence,
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

    if raw.lang == "csharp":
        dst_norm = dst_raw
        resolved = _resolve_csharp_namespace(dst_raw, csharp_map)
        if resolved:
            dst_kind = DepDstKind.INTERNAL_FILE
            dst_resolved_path = resolved
            confidence = min(confidence, 0.8)
        else:
            dst_kind = DepDstKind.EXTERNAL_PKG
        dst_kind, dst_resolved_path, confidence = _maybe_infer_internal(
            raw.src,
            dst_raw,
            dst_norm,
            file_set,
            dst_kind,
            dst_resolved_path,
            confidence,
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

    resolved_generic = _resolve_generic_absolute(dst_raw, file_set, source_roots)
    if resolved_generic:
        dst_kind = DepDstKind.INTERNAL_FILE
        dst_resolved_path = resolved_generic
        confidence = min(confidence, 0.8)
    else:
        resolved_relative = _resolve_relative_path(raw.src, dst_raw, file_set)
        if resolved_relative:
            dst_kind = DepDstKind.INTERNAL_FILE
            dst_resolved_path = resolved_relative
            confidence = min(confidence, 0.8)
    dst_kind, dst_resolved_path, confidence = _maybe_infer_internal(
        raw.src,
        dst_raw,
        dst_norm,
        file_set,
        dst_kind,
        dst_resolved_path,
        confidence,
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
    src_path: str,
    module_name: str,
    level: int,
    module_map: dict[str, str],
    file_set: set[str],
    symbol: str | None,
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
        resolved = module_map.get(parent)
        if resolved:
            return resolved

    base_dir = Path(src_path).parent
    for _ in range(max(0, level - 1)):
        base_dir = base_dir.parent
    target = module_name or (symbol or "")
    module_path = target.replace(".", "/") if target else ""
    candidates = []
    if module_path:
        candidates.extend(
            [
                f"{base_dir.as_posix()}/{module_path}.py",
                f"{base_dir.as_posix()}/{module_path}/__init__.py",
            ]
        )
    else:
        candidates.append(f"{base_dir.as_posix()}/__init__.py")
    for candidate in candidates:
        if candidate in file_set:
            return candidate
    return None


def _resolve_js_relative(src_path: str, dst_raw: str, file_set: set[str]) -> str | None:
    src_dir = Path(src_path).parent
    base = _normalize_posix_path((src_dir / dst_raw).as_posix())
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


def _resolve_js_absolute(
    dst_raw: str, file_set: set[str], source_roots: list[str]
) -> str | None:
    if not source_roots:
        return None
    candidates: list[str] = []
    for root in source_roots:
        base = f"{root}/{dst_raw}"
        candidates.extend(
            [
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
        )
    for candidate in candidates:
        if candidate in file_set:
            return candidate
    return None


def _resolve_generic_absolute(
    dst_raw: str, file_set: set[str], source_roots: list[str]
) -> str | None:
    if not source_roots:
        return None
    for root in source_roots:
        candidate = f"{root}/{dst_raw}"
        if candidate in file_set:
            return candidate
    return None


def _normalize_posix_path(path: str) -> str:
    parts = []
    for part in PurePosixPath(path).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _resolve_relative_path(
    src_path: str, dst_raw: str, file_set: set[str]
) -> str | None:
    if not (dst_raw.startswith("./") or dst_raw.startswith("../")):
        return None
    base = PurePosixPath(src_path).parent / dst_raw
    normalized = _normalize_posix_path(base.as_posix())
    if normalized in file_set:
        return normalized
    return None


def _infer_internal_from_nodes(
    src_path: str, dst_raw: str, dst_norm: str, file_set: set[str]
) -> str | None:
    candidates: set[str] = set()
    for value in (dst_norm, dst_raw):
        if not value:
            continue
        cleaned = value.strip().strip("\"'").replace("\\", "/")
        candidates.add(cleaned)
        if "/" in cleaned:
            candidates.add(cleaned)
        module_path = cleaned.replace(".", "/")
        if module_path:
            candidates.update(
                {
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                    f"{module_path}.js",
                    f"{module_path}.jsx",
                    f"{module_path}.ts",
                    f"{module_path}.tsx",
                    f"{module_path}/index.js",
                    f"{module_path}/index.jsx",
                    f"{module_path}/index.ts",
                    f"{module_path}/index.tsx",
                    f"{module_path}.go",
                    f"{module_path}.java",
                    f"{module_path}.rs",
                    f"{module_path}.c",
                    f"{module_path}.h",
                    f"{module_path}.cpp",
                    f"{module_path}.hpp",
                }
            )
    matches = [candidate for candidate in candidates if candidate in file_set]
    if matches:
        return _pick_best_candidate(src_path, matches)
    return _resolve_by_dir_tree(src_path, dst_raw, file_set)


def _maybe_infer_internal(
    src_path: str,
    dst_raw: str,
    dst_norm: str,
    file_set: set[str],
    dst_kind: DepDstKind,
    dst_resolved_path: str | None,
    confidence: float,
) -> tuple[DepDstKind, str | None, float]:
    if dst_resolved_path:
        return dst_kind, dst_resolved_path, confidence
    inferred = _infer_internal_from_nodes(src_path, dst_raw, dst_norm, file_set)
    if inferred:
        return DepDstKind.INTERNAL_FILE, inferred, min(confidence, 0.7)
    return dst_kind, dst_resolved_path, confidence


def _candidate_source_roots(repo_index: RepoIndex) -> list[str]:
    top_dirs: set[str] = set()
    py_dirs: set[str] = set()
    for entry in repo_index.files:
        parts = entry.path.split("/")
        if len(parts) > 1:
            top = parts[0]
            top_dirs.add(top)
            if entry.path.endswith(".py"):
                py_dirs.add(top)
    common = {
        "src",
        "app",
        "lib",
        "packages",
        "client",
        "server",
        "php",
        "csharp",
        "CSharp",
    }
    roots = py_dirs | (common & top_dirs)
    return sorted(roots)


def _resolve_by_dir_tree(src_path: str, dst_raw: str, file_set: set[str]) -> str | None:
    cleaned = dst_raw.strip().strip("\"'").replace("\\", "/")
    if not cleaned or cleaned.startswith((".", "/")):
        return None
    base = cleaned.replace(".", "/")
    suffixes = [
        f"{base}.py",
        f"{base}/__init__.py",
        f"{base}.js",
        f"{base}.jsx",
        f"{base}.ts",
        f"{base}.tsx",
        f"{base}/index.js",
        f"{base}/index.jsx",
        f"{base}/index.ts",
        f"{base}/index.tsx",
        f"{base}.go",
        f"{base}.java",
        f"{base}.rs",
        f"{base}.c",
        f"{base}.h",
        f"{base}.cpp",
        f"{base}.hpp",
    ]
    matches = [path for path in file_set if path.endswith(tuple(suffixes))]
    if not matches:
        return None
    return _pick_best_candidate(src_path, matches)


def _pick_best_candidate(src_path: str, candidates: list[str]) -> str:
    src_parts = PurePosixPath(src_path).parts
    src_dir_parts = src_parts[:-1]

    def score(path: str) -> tuple[int, int, str]:
        parts = PurePosixPath(path).parts
        common = 0
        for a, b in zip(src_dir_parts, parts[:-1]):
            if a != b:
                break
            common += 1
        return (common, -len(parts), path)

    return max(candidates, key=score)


def _build_csharp_module_map(
    repo_index: RepoIndex, source_roots: list[str]
) -> dict[str, str]:
    module_map: dict[str, str] = {}
    for entry in repo_index.files:
        if not entry.path.endswith(".cs"):
            continue
        module = entry.path[:-3].replace("/", ".")
        module_map[module] = entry.path
        for root in source_roots:
            prefix = f"{root}/"
            if entry.path.startswith(prefix):
                module_map[entry.path[len(prefix) : -3].replace("/", ".")] = entry.path
    return module_map


def _resolve_csharp_namespace(namespace: str, module_map: dict[str, str]) -> str | None:
    if not namespace:
        return None
    if namespace in module_map:
        return module_map[namespace]
    parts = namespace.split(".")
    if not parts:
        return None
    candidate = parts[-1]
    if candidate in module_map:
        return module_map[candidate]
    # Try suffix matches to allow root stripping
    for i in range(1, len(parts)):
        suffix = ".".join(parts[i:])
        if suffix in module_map:
            return module_map[suffix]
    return None


def _build_python_module_map(
    repo_index: RepoIndex, source_roots: list[str]
) -> dict[str, str]:
    module_map: dict[str, str] = {}
    for entry in repo_index.files:
        if entry.path.endswith(".py"):
            module = entry.path[:-3].replace("/", ".")
            module_map[module] = entry.path
            for root in source_roots:
                prefix = f"{root}/"
                if entry.path.startswith(prefix):
                    module_map[entry.path[len(prefix) : -3].replace("/", ".")] = (
                        entry.path
                    )
            if entry.path.endswith("/__init__.py"):
                pkg = entry.path[:-12].replace("/", ".")
                if pkg:
                    module_map[pkg] = entry.path
                for root in source_roots:
                    prefix = f"{root}/"
                    if entry.path.startswith(prefix):
                        pkg_src = entry.path[len(prefix) : -12].replace("/", ".")
                        if pkg_src:
                            module_map[pkg_src] = entry.path
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


_probe_tree_sitter()
