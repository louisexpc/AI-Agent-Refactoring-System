"""Go Language Plugin（stub）：預留 Go 語言的測試生成與執行。

尚未實作，所有方法拋出 NotImplementedError。
預留執行框架：go test -cover, go build。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runner.test_gen.plugins import LanguagePlugin, TestRunResult


class GoPlugin(LanguagePlugin):
    """Go 語言插件（stub）。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        raise NotImplementedError("Go plugin not yet implemented")

    def run_with_coverage(
        self,
        script_path: Path,
        work_dir: Path,
        timeout: int,
    ) -> TestRunResult:
        raise NotImplementedError("Go plugin not yet implemented")

    def generate_test_file(
        self,
        new_source_code: str,
        module_paths: list[str],
        golden_values: dict[str, Any],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        raise NotImplementedError("Go plugin not yet implemented")

    def run_tests(
        self,
        test_file_path: Path,
        work_dir: Path,
        timeout: int,
    ) -> TestRunResult:
        raise NotImplementedError("Go plugin not yet implemented")

    def check_build(
        self,
        repo_dir: Path,
        timeout: int,
    ) -> tuple[bool, str]:
        raise NotImplementedError("Go plugin not yet implemented")
