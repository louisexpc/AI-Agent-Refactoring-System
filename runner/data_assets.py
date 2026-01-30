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
    repo_dir: Path

    def build(self, repo_index: RepoIndex) -> DbAssetsIndex:
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
        if "/migrations/" in path:
            return "migration"
        if "schema" in path:
            return "schema"
        if "/seed" in path or "/seeds" in path:
            return "seed"
        return "sql"

    @staticmethod
    def _sha1(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass
class SqlInventoryExtractor:
    repo_dir: Path

    def build(self, repo_index: RepoIndex) -> SqlInventory:
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
        if len(text) <= limit:
            return text
        return text[:limit]

    @staticmethod
    def _sha1(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
