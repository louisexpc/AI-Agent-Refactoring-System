"""Phase 1：從 DepGraph 過濾目標語言的來源檔案。

讀取 DepGraph 節點，依據副檔名 / lang 過濾出可測試的檔案，
並讀取其完整原始碼。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import DepGraph, RepoIndex
from shared.test_types import SourceFile

# 副檔名 → 語言對應
_EXT_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".ts": "typescript",
}


@dataclass
class FileFilter:
    """從 DepGraph 過濾目標語言檔案並讀取內容。

    Args:
        repo_dir: snapshot 中的 repo 目錄。
    """

    repo_dir: Path

    def filter(
        self,
        dep_graph: DepGraph,
        repo_index: RepoIndex,
        target_language: str = "python",
    ) -> list[SourceFile]:
        """過濾出目標語言的來源檔案。

        Args:
            dep_graph: 依賴圖。
            repo_index: 檔案索引。
            target_language: 目標語言。

        Returns:
            來源檔案清單。
        """
        results: list[SourceFile] = []

        for node in dep_graph.nodes:
            file_path = self.repo_dir / node.path
            if not file_path.is_file():
                continue

            # 判斷語言：優先用 node.lang，fallback 用副檔名
            lang = self._resolve_lang(node.lang, node.ext, file_path.suffix)
            if lang is None:
                continue

            # 只保留目標語言的檔案
            if lang != target_language:
                continue

            results.append(SourceFile(path=node.path, lang=lang))

        return results

    def filter_single(self, file_path: str) -> SourceFile | None:
        """讀取單一檔案並回傳 SourceFile。

        供 run_module_test 使用。

        Args:
            file_path: 檔案相對路徑（相對於 repo root）。

        Returns:
            SourceFile 或 None（檔案不存在時）。
        """
        full_path = self.repo_dir / file_path
        if not full_path.is_file():
            return None

        lang = _EXT_LANG_MAP.get(full_path.suffix)
        if lang is None:
            return None

        return SourceFile(path=file_path, lang=lang)

    def _resolve_lang(
        self,
        node_lang: str | None,
        node_ext: str | None,
        suffix: str,
    ) -> str | None:
        """從 node 資訊推斷語言。

        Args:
            node_lang: DepNode 的 lang 欄位。
            node_ext: DepNode 的 ext 欄位。
            suffix: 檔案副檔名。

        Returns:
            語言名稱或 None。
        """
        if node_lang and node_lang in ("python", "go", "javascript", "typescript"):
            return node_lang

        ext = node_ext or suffix
        return _EXT_LANG_MAP.get(ext)
