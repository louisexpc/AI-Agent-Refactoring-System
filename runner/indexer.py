from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pathspec

from shared.ingestion_types import FileEntry, RepoIndex, ScopeCandidate

DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "node_modules/",
    "dist/",
    "build/",
    ".tox/",
    ".eggs/",
    "*.pyc",
]


@dataclass
class RepoIndexer:
    """建立 repo 檔案索引與指標資訊。

    Args:
        repo_dir: snapshot repo 的根目錄。
    """

    repo_dir: Path

    def build_index(self) -> RepoIndex:
        """掃描檔案並產出 `RepoIndex`。

        Returns:
            `RepoIndex`。
        """
        spec = self._load_gitignore()
        files: list[FileEntry] = []
        total_bytes = 0

        for path in self._iter_files():
            rel_path = path.relative_to(self.repo_dir).as_posix()
            if spec.match_file(rel_path):
                continue
            size = path.stat().st_size
            total_bytes += size
            files.append(
                FileEntry(
                    path=rel_path,
                    ext=path.suffix.lower() or None,
                    bytes=size,
                    sha1=self._sha1(path),
                )
            )

        indicators = self._detect_indicators({f.path for f in files})
        return RepoIndex(
            root=".",
            file_count=len(files),
            total_bytes=total_bytes,
            files=files,
            indicators=indicators,
        )

    def _iter_files(self) -> Iterable[Path]:
        """迭代 repo 中的所有檔案。"""
        for path in self.repo_dir.rglob("*"):
            if path.is_file():
                yield path

    def _load_gitignore(self) -> pathspec.PathSpec:
        """載入 .gitignore 規則。

        Returns:
            `PathSpec`。
        """
        patterns = list(DEFAULT_IGNORE_PATTERNS)
        gitignore_path = self.repo_dir / ".gitignore"
        if gitignore_path.exists():
            patterns.extend(gitignore_path.read_text(encoding="utf-8").splitlines())
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def _sha1(self, path: Path) -> str:
        """計算檔案內容的 sha1。

        Args:
            path: 檔案路徑。

        Returns:
            sha1 hex 字串。
        """
        hasher = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _detect_indicators(self, file_paths: set[str]) -> list[str]:
        """偵測 build/test 相關指標檔。

        Args:
            file_paths: 相對路徑集合。

        Returns:
            指標字串列表。
        """
        indicators: list[str] = []
        indicator_files = {
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "pom.xml",
            "build.gradle",
            "composer.json",
            "pytest.ini",
        }
        for name in indicator_files:
            if name in file_paths:
                indicators.append(name)

        template_exts = {".erb", ".jinja", ".jinja2", ".ejs"}
        has_templates = any(
            path.endswith(tuple(template_exts))
            or "/templates/" in path
            or "/views/" in path
            for path in file_paths
        )
        if has_templates:
            indicators.append("templates")

        return sorted(set(indicators))


@dataclass
class ScopeClassifier:
    """根據指標檔推論 scope 資訊。

    Args:
        repo_dir: snapshot repo 的根目錄。
    """

    repo_dir: Path

    def classify(self, repo_index: RepoIndex) -> list[ScopeCandidate]:
        """產生 scope candidates。

        Args:
            repo_index: RepoIndexer 產出的索引資料。

        Returns:
            `ScopeCandidate` 列表。
        """
        indicators = set(repo_index.indicators)
        language = None
        build_tool = None
        test_tool = None
        risk_flags: list[str] = []

        if {"pyproject.toml", "requirements.txt"} & indicators:
            language = "python"
            build_tool = "uv" if "pyproject.toml" in indicators else "pip"
            test_tool = "pytest" if "pytest.ini" in indicators else None

        if "package.json" in indicators:
            if language and language != "python":
                language = "multi"
            elif language == "python":
                language = "multi"
            else:
                language = "node"
            build_tool = build_tool or "npm"
            test_tool = test_tool or "npm test"

        if "templates" in indicators:
            risk_flags.append("templates-detected")

        scope = ScopeCandidate(
            scope_id="scope-root",
            root_path=".",
            language=language,
            build_tool=build_tool,
            test_tool=test_tool,
            risk_flags=risk_flags,
        )
        return [scope]
