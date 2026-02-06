"""Module-level Test Emitter：消費 golden values 生成 characterization test。

讀取 after_files（重構後的原始碼）+ golden output，
由 LanguagePlugin 生成目標語言的 test file。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.test_gen.dep_resolver import resolve_dependency_context
from runner.test_gen.plugins import LanguagePlugin
from shared.ingestion_types import DepGraph
from shared.test_types import (
    EmittedTestFile,
    GoldenRecord,
    SourceFile,
    TestGuidance,
)

logger = logging.getLogger(__name__)


@dataclass
class ModuleTestEmitter:
    """Module-level test emitter：為重構後的 module 生成 characterization test。

    Attributes:
        repo_dir: 重構後程式碼的 repo 目錄。
        target_language: 目標語言。
    """

    repo_dir: Path
    target_language: str = "python"

    def emit(
        self,
        after_files: list[SourceFile],
        golden_records: list[GoldenRecord],
        plugin: LanguagePlugin,
        llm_client: Any,
        guidance: TestGuidance | None = None,
        dep_graph: DepGraph | None = None,
    ) -> EmittedTestFile:
        """為一組 after_files 生成 characterization test file。

        Args:
            after_files: module mapping 中的新檔案清單。
            golden_records: 對應的 golden output。
            plugin: 語言插件。
            llm_client: LLM 呼叫介面。
            guidance: 測試指引。
            dep_graph: 依賴圖。

        Returns:
            產出的測試檔案。
        """
        # 聚合 after_files 原始碼
        source_code = self._aggregate_source(after_files)
        module_paths = [sf.path for sf in after_files]

        # 收集依賴 signatures
        dep_signatures = self._collect_dep_signatures(after_files, dep_graph)

        # 聚合 golden values
        golden_values: dict[str, Any] = {}
        for rec in golden_records:
            if isinstance(rec.output, dict):
                golden_values.update(rec.output)
            elif rec.output is not None:
                golden_values[rec.file_path] = rec.output

        # 用 plugin 生成 test file（帶 retry）
        guidance_dict = guidance.model_dump() if guidance else None
        content = self._generate_test_with_retry(
            plugin=plugin,
            source_code=source_code,
            module_paths=module_paths,
            golden_values=golden_values,
            dep_signatures=dep_signatures,
            guidance_dict=guidance_dict,
            llm_client=llm_client,
            max_retries=3,
        )

        test_path = self._derive_test_path(module_paths)
        source_file_str = (
            module_paths[0] if len(module_paths) == 1 else ",".join(module_paths)
        )

        return EmittedTestFile(
            path=test_path,
            language=self.target_language,
            content=content,
            source_file=source_file_str,
        )

    def _aggregate_source(self, files: list[SourceFile]) -> str:
        """聚合多個檔案的原始碼，帶路徑標記。"""
        if len(files) == 1:
            return files[0].read_content(self.repo_dir)

        sections: list[str] = []
        for sf in files:
            content = sf.read_content(self.repo_dir)
            sections.append(
                f"File: {sf.path}\n"
                f"Directory: {str(Path(sf.path).parent)}\n"
                f"Module name: {Path(sf.path).stem}\n"
                f"```\n{content}\n```"
            )
        return "\n\n".join(sections)

    def _collect_dep_signatures(
        self,
        files: list[SourceFile],
        dep_graph: DepGraph | None,
    ) -> str:
        """收集依賴 signatures。"""
        if dep_graph is None:
            return ""

        seen: set[str] = set()
        parts: list[str] = []
        for sf in files:
            ctx = resolve_dependency_context(dep_graph, sf.path, self.repo_dir)
            if ctx and ctx not in seen:
                seen.add(ctx)
                parts.append(ctx)
        return "\n".join(parts)

    def _derive_test_path(self, module_paths: list[str]) -> str:
        """根據模組路徑推導測試檔路徑。"""
        p = Path(module_paths[0])
        ext_map = {
            "python": ".py",
            "go": ".go",
            "typescript": ".test.ts",
            "javascript": ".test.js",
        }
        ext = ext_map.get(self.target_language, ".py")

        if self.target_language == "go":
            # Go: leaderboard.go → leaderboard_test.go
            return str(p.parent / f"{p.stem}_test{ext}")
        return str(p.parent / f"test_{p.stem}{ext}")

    def _generate_test_with_retry(
        self,
        plugin: LanguagePlugin,
        source_code: str,
        module_paths: list[str],
        golden_values: dict[str, Any],
        dep_signatures: str,
        guidance_dict: dict[str, Any] | None,
        llm_client: Any,
        max_retries: int = 3,
    ) -> str:
        """生成 test file，如果編譯失敗則 retry。

        Args:
            plugin: 語言插件。
            source_code: 原始碼。
            module_paths: 模組路徑。
            golden_values: Golden values。
            dep_signatures: 依賴 signatures。
            guidance_dict: 測試指引。
            llm_client: LLM 客戶端。
            max_retries: 最大重試次數。

        Returns:
            生成的 test content。
        """
        error_feedback = None

        for attempt in range(max_retries):
            if attempt > 0:
                logger.info(
                    f"Retry test generation, attempt {attempt + 1}/{max_retries}"
                )

            # 如果是 retry，在 guidance 中加入錯誤訊息
            if error_feedback and guidance_dict:
                guidance_dict["compilation_error"] = error_feedback
            elif error_feedback:
                guidance_dict = {"compilation_error": error_feedback}

            # 生成 test
            content = plugin.generate_test_file(
                new_source_code=source_code,
                module_paths=module_paths,
                golden_values=golden_values,
                dep_signatures=dep_signatures,
                guidance=guidance_dict,
                llm_client=llm_client,
            )

            # 快速語法檢查（使用 plugin 的方法）
            compile_ok, error_msg = plugin.check_test_syntax(content)

            if compile_ok:
                if attempt > 0:
                    logger.info(f"Test generation succeeded on attempt {attempt + 1}")
                return content

            # 編譯失敗，準備 retry
            error_feedback = (
                "Previous test had syntax/compile errors:\n"
                f"{error_msg}\n"
                "Please fix these errors and regenerate."
            )
            short_error = error_msg[:200]
            logger.warning(
                "Test compilation failed on attempt %d: %s",
                attempt + 1,
                short_error,
            )

        # 所有 retry 都失敗，返回最後一次生成的 test
        logger.error(
            "Test generation failed after %d attempts, using last generated test",
            max_retries,
        )
        return content
