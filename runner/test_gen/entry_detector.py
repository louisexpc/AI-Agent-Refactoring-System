"""Phase 1：從 DepGraph 識別可測試的 entry points。

讀取 DepGraphL0 的節點與邊，結合原始碼解析，
找出可作為測試目標的函式或端點。
理論上應該不是由我偵測，之後可以換掉
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import DepGraphL0, RepoIndex
from shared.test_types import EntryIndex, TestableEntry

# 支援的語言 → 函式簽名正規表達式
_FUNCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    ".py": re.compile(
        r"^\s*(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<sig>[^)]*)\)",
        re.MULTILINE,
    ),
    ".go": re.compile(
        r"^func\s+(?:\([^)]*\)\s+)?(?P<name>\w+)\s*\((?P<sig>[^)]*)\)",
        re.MULTILINE,
    ),
    ".js": re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\((?P<sig>[^)]*)\)",
        re.MULTILINE,
    ),
    ".ts": re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\((?P<sig>[^)]*)\)",
        re.MULTILINE,
    ),
}


@dataclass
class EntryDetector:
    """從 DepGraph 與原始碼中識別可測試 entry points。

    Args:
        repo_dir: snapshot 中的 repo 目錄。
    """

    repo_dir: Path

    def build(
        self,
        dep_graph: DepGraphL0,
        repo_index: RepoIndex,
    ) -> EntryIndex:
        """掃描 DepGraph 節點，提取函式簽名作為可測試 entry。

        Args:
            dep_graph: L0 依賴圖。
            repo_index: 檔案索引。

        Returns:
            可測試 entry point 索引。
        """
        entries: list[TestableEntry] = []

        for node in dep_graph.nodes:
            file_path = self.repo_dir / node.path
            if not file_path.is_file():
                continue

            ext = file_path.suffix
            pattern = _FUNCTION_PATTERNS.get(ext)
            if pattern is None:
                continue

            source = file_path.read_text(encoding="utf-8", errors="replace")
            for match in pattern.finditer(source):
                func_name = match.group("name")
                sig = match.group("sig").strip()
                # 跳過私有 / dunder 函式
                if func_name.startswith("_"):
                    continue
                entry_id = f"{node.path}::{func_name}"
                entries.append(
                    TestableEntry(
                        entry_id=entry_id,
                        module_path=node.path,
                        function_name=func_name,
                        signature=sig or None,
                        dep_node_id=node.node_id,
                    ),
                )

        return EntryIndex(entries=entries)
