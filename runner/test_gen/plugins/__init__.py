"""Language Plugin 架構：抽象語言相關的測試操作。

每個語言 plugin 負責：
1. 生成 golden capture 腳本（舊 code）
2. 執行腳本並收集 coverage
3. 生成 characterization test file（新 code）
4. 執行 test file 並收集結果
5. Build/compile 檢查
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TestRunResult:
    """語言 plugin 執行腳本或測試後的結果。

    Attributes:
        exit_code: 程式結束碼。
        stdout: 標準輸出。
        stderr: 標準錯誤。
        coverage_pct: 行覆蓋率百分比。
    """

    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    coverage_pct: float | None = None


class LanguagePlugin(ABC):
    """語言插件抽象基底類別。

    舊 code 和新 code 各用對應語言的 plugin instance。
    """

    @abstractmethod
    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """LLM 生成呼叫腳本，用於捕獲 golden output。

        Args:
            source_code: 完整原始碼（可能是多檔聚合）。
            module_paths: 檔案路徑清單。
            dep_signatures: 依賴檔案的 signatures context。
            guidance: 測試指引（side_effects, mock_recommendations 等）。
            llm_client: LLM 呼叫介面。

        Returns:
            可執行的腳本原始碼字串。
        """

    @abstractmethod
    def run_with_coverage(
        self,
        script_path: Path,
        work_dir: Path,
        timeout: int,
    ) -> TestRunResult:
        """執行腳本並收集 coverage。

        Args:
            script_path: 腳本檔案路徑。
            work_dir: 工作目錄（通常是 repo root）。
            timeout: 超時秒數。

        Returns:
            TestRunResult。
        """

    @abstractmethod
    def generate_test_file(
        self,
        new_source_code: str,
        module_paths: list[str],
        golden_values: dict[str, Any],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """LLM 生成目標語言的 test file。

        Args:
            new_source_code: 新 code 完整原始碼（可能是多檔聚合）。
            module_paths: 新 code 檔案路徑清單。
            golden_values: golden output 的值（key → value）。
            dep_signatures: 依賴檔案的 signatures context。
            guidance: 測試指引。
            llm_client: LLM 呼叫介面。

        Returns:
            test file 原始碼字串。
        """

    @abstractmethod
    def run_tests(
        self,
        test_file_path: Path,
        work_dir: Path,
        timeout: int,
    ) -> TestRunResult:
        """執行 test file 並收集結果。

        Args:
            test_file_path: test file 路徑。
            work_dir: 工作目錄。
            timeout: 超時秒數。

        Returns:
            TestRunResult。
        """

    @abstractmethod
    def check_build(
        self,
        repo_dir: Path,
        timeout: int,
    ) -> tuple[bool, str]:
        """檢查 code 是否能成功 build/compile。

        Args:
            repo_dir: repo 目錄。
            timeout: 超時秒數。

        Returns:
            (success, output) 元組。
        """


_PLUGIN_REGISTRY: dict[str, type[LanguagePlugin]] = {}


def register_plugin(language: str, plugin_class: type[LanguagePlugin]) -> None:
    """註冊語言 plugin。

    Args:
        language: 語言識別字串（如 "python", "go"）。
        plugin_class: LanguagePlugin 子類別。
    """
    _PLUGIN_REGISTRY[language] = plugin_class


def get_plugin(language: str) -> LanguagePlugin:
    """取得語言 plugin instance。

    Args:
        language: 語言識別字串。

    Returns:
        LanguagePlugin instance。

    Raises:
        ValueError: 未註冊的語言。
    """
    plugin_class = _PLUGIN_REGISTRY.get(language)
    if plugin_class is None:
        raise ValueError(f"No plugin registered for language: {language}")
    return plugin_class()


def _auto_register() -> None:
    """自動註冊內建 plugins。"""
    from runner.test_gen.plugins.go_plugin import GoPlugin
    from runner.test_gen.plugins.java_plugin import JavaPlugin
    from runner.test_gen.plugins.python_plugin import PythonPlugin

    register_plugin("python", PythonPlugin)
    register_plugin("go", GoPlugin)
    register_plugin("java", JavaPlugin)


_auto_register()
