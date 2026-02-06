from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from shared.ingestion_types import (
    DbAsset,
    DbAssetsIndex,
    RepoIndex,
    SqlInventory,
    SqlItem,
)

SQL_KEYWORDS = re.compile(
    r"\b(select|insert|update|delete|with|create|alter|drop)\b",
    re.IGNORECASE,
)
SQL_KEYWORDS_STRICT = re.compile(
    r"\b(select|insert|update|delete|create|alter|drop)\b",
    re.IGNORECASE,
)
STRING_LITERAL = re.compile(r"(['\"])(?P<text>.*?)(\1)")


@dataclass
class DbAssetIndexer:
    """索引資料庫資產（schema/migrations/seed/sql）。

    Args:
        repo_dir: snapshot repo 的根目錄。
    """

    repo_dir: Path

    def build(self, repo_index: RepoIndex) -> DbAssetsIndex:
        """從 repo_index 篩選 DB 相關檔案。

        Args:
            repo_index: RepoIndexer 產出的索引資料。

        Returns:
            `DbAssetsIndex`。
        """
        assets: list[DbAsset] = []
        for entry in repo_index.files:
            path = entry.path
            lower_path = path.lower()
            if not self._is_db_asset(lower_path):
                continue
            kind = self._classify_kind(lower_path)
            assets.append(
                DbAsset(
                    asset_id=self._sha1(path),
                    scope_id=None,
                    kind=kind,
                    path=path,
                )
            )
        return DbAssetsIndex(assets=assets)

    @staticmethod
    def _is_db_asset(path: str) -> bool:
        """判斷路徑是否為 DB asset。

        Args:
            path: 檔案相對路徑（小寫）。

        Returns:
            是否屬於 DB asset。
        """
        return (
            path.endswith(".sql")
            or "/migrations/" in path
            or "/schema/" in path
            or path.endswith("schema.sql")
            or "/seed" in path
            or "/seeds" in path
            or path.endswith("schema.rb")
        )

    @staticmethod
    def _classify_kind(path: str) -> str:
        """依路徑推測 asset 種類。

        Args:
            path: 檔案相對路徑（小寫）。

        Returns:
            asset 類型字串。
        """
        if "/migrations/" in path:
            return "migration"
        if "schema" in path:
            return "schema"
        if "/seed" in path or "/seeds" in path:
            return "seed"
        return "sql"

    @staticmethod
    def _sha1(text: str) -> str:
        """產生 sha1 雜湊。

        Args:
            text: 原始字串。

        Returns:
            sha1 hex 字串。
        """
        return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass
class SqlInventoryExtractor:
    """抽取 embedded SQL 與純 SQL 檔內容。

    Args:
        repo_dir: snapshot repo 的根目錄。
    """

    repo_dir: Path

    def build(self, repo_index: RepoIndex) -> SqlInventory:
        """掃描 repo 產出 SQL inventory。

        Args:
            repo_index: RepoIndexer 產出的索引資料。

        Returns:
            `SqlInventory`。
        """
        items: list[SqlItem] = []
        for entry in repo_index.files:
            rel_path = entry.path
            if not self._should_scan(rel_path):
                continue
            file_path = self.repo_dir / rel_path
            try:
                lines = file_path.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines()
            except OSError:
                continue
            if rel_path.lower().endswith(".sql"):
                items.extend(self._from_sql_file(rel_path, lines))
            else:
                items.extend(self._from_code_file(rel_path, lines))
        return SqlInventory(items=items)

    def _from_sql_file(self, rel_path: str, lines: list[str]) -> list[SqlItem]:
        """從 .sql 檔案抽取 SQL 片段。

        Args:
            rel_path: 相對路徑。
            lines: 檔案內容行列表。

        Returns:
            `SqlItem` 列表。
        """
        items: list[SqlItem] = []
        for idx, line in enumerate(lines, start=1):
            if not SQL_KEYWORDS.search(line):
                continue
            snippet = self._truncate(line.strip())
            sql_kind = self._classify_sql(snippet)
            sql_hash = self._sha1(snippet)
            items.append(
                SqlItem(
                    sql_id=sql_hash,
                    file_path=rel_path,
                    start_line=idx,
                    end_line=idx,
                    sql_hash=sql_hash,
                    sql_kind=sql_kind,
                    snippet=snippet,
                )
            )
        return items

    def _from_code_file(self, rel_path: str, lines: list[str]) -> list[SqlItem]:
        """從程式碼檔案抽取 string literal SQL。

        Args:
            rel_path: 相對路徑。
            lines: 檔案內容行列表。

        Returns:
            `SqlItem` 列表。
        """
        items: list[SqlItem] = []
        for idx, line in enumerate(lines, start=1):
            if not SQL_KEYWORDS_STRICT.search(line):
                continue
            for match in STRING_LITERAL.finditer(line):
                text = match.group("text")
                if not SQL_KEYWORDS_STRICT.search(text):
                    continue
                snippet = self._truncate(text.strip())
                sql_kind = self._classify_sql(snippet)
                sql_hash = self._sha1(snippet)
                items.append(
                    SqlItem(
                        sql_id=sql_hash,
                        file_path=rel_path,
                        start_line=idx,
                        end_line=idx,
                        sql_hash=sql_hash,
                        sql_kind=sql_kind,
                        snippet=snippet,
                    )
                )
        return items

    @staticmethod
    def _should_scan(path: str) -> bool:
        """判斷檔案是否需要 SQL 掃描。

        Args:
            path: 相對路徑。

        Returns:
            是否需掃描。
        """
        lower_path = path.lower()
        if lower_path.endswith(".sql"):
            return True
        allowed_exts = {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".kt",
            ".go",
            ".rb",
            ".php",
            ".cs",
            ".scala",
        }
        return Path(lower_path).suffix in allowed_exts

    @staticmethod
    def _classify_sql(text: str) -> str:
        """依關鍵字推測 SQL 類型。

        Args:
            text: SQL 片段文字。

        Returns:
            "ddl" | "dml" | "unknown"。
        """
        lowered = text.lower()
        if any(keyword in lowered for keyword in ("create", "alter", "drop")):
            return "ddl"
        if any(
            keyword in lowered
            for keyword in ("insert", "update", "delete", "select", "with")
        ):
            return "dml"
        return "unknown"

    @staticmethod
    def _truncate(text: str, limit: int = 300) -> str:
        """裁剪過長的 SQL snippet。

        Args:
            text: 原始文字。
            limit: 最大長度。

        Returns:
            截斷後文字。
        """
        if len(text) <= limit:
            return text
        return text[:limit]

    @staticmethod
    def _sha1(text: str) -> str:
        """產生 sha1 雜湊。

        Args:
            text: 原始文字。

        Returns:
            sha1 hex 字串。
        """
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
