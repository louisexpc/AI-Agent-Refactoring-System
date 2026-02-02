"""共用依賴解析 helper：從 dep_graph 解析依賴檔案並提取 signatures。

提供兩個公開函式：
- ``extract_signatures``: 用 AST 提取 Python class/function 簽名。
- ``resolve_dependency_context``: 解析依賴檔案並回傳 signatures-only context。
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from shared.ingestion_types import DepGraph

logger = logging.getLogger(__name__)

_STDLIB_MODULES: frozenset[str] = frozenset(
    {
        "abc",
        "collections",
        "datetime",
        "functools",
        "html",
        "itertools",
        "json",
        "math",
        "os",
        "pathlib",
        "random",
        "re",
        "sys",
        "time",
        "typing",
        "unittest",
    }
)


def extract_signatures(source_code: str) -> str:
    """用 Python ast 提取 class/function 簽名 + docstring，去掉實作 body。

    Args:
        source_code: Python 原始碼。

    Returns:
        僅含簽名與 docstring 的精簡原始碼。
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # 非 Python 或語法錯誤，fallback 回截斷原始碼
        lines = source_code.splitlines()
        return "\n".join(lines[:200])

    parts: list[str] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            parts.append(_format_class(node, source_code))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(_format_function(node, source_code))

    if not parts:
        # 沒有 class/function（純腳本），fallback 回截斷原始碼
        lines = source_code.splitlines()
        return "\n".join(lines[:200])

    return "\n\n".join(parts)


def _format_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
) -> str:
    """格式化單一 function 簽名。"""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    sig = f"{prefix} {node.name}({ast.unparse(node.args)})"
    if node.returns:
        sig += f" -> {ast.unparse(node.returns)}"
    sig += ":"

    docstring = ast.get_docstring(node)
    if docstring:
        sig += f'\n    """{docstring}"""'
    sig += "\n    ..."
    return sig


def _format_class(node: ast.ClassDef, source: str) -> str:
    """格式化 class 簽名 + 方法簽名。"""
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    header = f"class {node.name}({bases}):" if bases else f"class {node.name}:"

    lines = [header]

    docstring = ast.get_docstring(node)
    if docstring:
        lines.append(f'    """{docstring}"""')

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
            sig = f"    {prefix} {item.name}({ast.unparse(item.args)})"
            if item.returns:
                sig += f" -> {ast.unparse(item.returns)}"
            sig += ":"
            method_doc = ast.get_docstring(item)
            if method_doc:
                sig += f'\n        """{method_doc}"""'
            sig += "\n        ..."
            lines.append(sig)

    return "\n".join(lines)


def resolve_dependency_context(
    dep_graph: DepGraph | None,
    module_path: str,
    repo_dir: Path,
    max_files: int = 5,
    max_lines_per_file: int = 200,
) -> str:
    """解析依賴檔案並回傳 signatures-only context string。

    Args:
        dep_graph: 依賴圖。
        module_path: 主檔案路徑（相對於 repo root）。
        repo_dir: repo 根目錄。
        max_files: 最多附帶幾個依賴檔案。
        max_lines_per_file: 每個依賴檔案最多幾行。

    Returns:
        格式化的依賴 context 文字，供 LLM prompt 使用。
    """
    if dep_graph is None or not dep_graph.edges:
        return "No dependency information available."

    module_dir = str(Path(module_path).parent)
    sections: list[str] = []

    for edge in dep_graph.edges:
        if edge.src != module_path:
            continue

        # 跳過標準庫
        if edge.dst_raw in _STDLIB_MODULES:
            continue

        # 解析檔案路徑
        resolved = _resolve_path(edge.dst_resolved_path, edge.dst_raw, module_dir)
        if resolved is None:
            continue

        full_path = repo_dir / resolved
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        signatures = extract_signatures(content)
        # 截斷
        sig_lines = signatures.splitlines()
        if len(sig_lines) > max_lines_per_file:
            sig_lines = sig_lines[:max_lines_per_file]
            sig_lines.append("# ... (truncated)")
        truncated = "\n".join(sig_lines)

        sections.append(f"--- {resolved} ---\n```\n{truncated}\n```")

        if len(sections) >= max_files:
            break

    if not sections:
        return "This file has no internal dependencies."

    return "\n\n".join(sections)


def _resolve_path(
    dst_resolved_path: str | None,
    dst_raw: str,
    module_dir: str,
) -> str | None:
    """嘗試解析依賴檔案的 repo 內相對路徑。

    Args:
        dst_resolved_path: dep_graph 提供的已解析路徑（可能為 None）。
        dst_raw: 原始 import 字串。
        module_dir: 主檔案所在目錄。

    Returns:
        解析後的相對路徑，或 None。
    """
    if dst_resolved_path:
        return dst_resolved_path

    # 手動解析：src 目錄 / dst_raw + .py
    candidate = str(Path(module_dir) / f"{dst_raw}.py")
    return candidate
