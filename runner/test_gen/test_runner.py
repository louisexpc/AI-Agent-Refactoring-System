"""Module-level Test Runner：執行 emitted test file 並收集結果。

將 ModuleTestEmitter 產出的測試檔案實際跑起來，
透過 LanguagePlugin 執行並收集 pass/fail 數量與 coverage。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from runner.test_gen.plugins import LanguagePlugin
from shared.test_types import (
    EmittedTestFile,
    TestItemResult,
    TestItemStatus,
    UnitTestResult,
)


@dataclass
class ModuleTestRunner:
    """執行單一 emitted test file 並收集結果。

    Attributes:
        work_dir: 被測程式碼的 repo 目錄。
        test_dir: emitted 測試檔案所在目錄。
        logs_dir: 執行日誌輸出目錄。
        timeout_sec: 測試超時秒數。
    """

    work_dir: Path
    test_dir: Path
    logs_dir: Path
    timeout_sec: int = 60
    source_dirs: list[str] | None = None

    def run(
        self,
        test_file: EmittedTestFile,
        plugin: LanguagePlugin,
    ) -> UnitTestResult:
        """執行 test file 並回傳結果。

        Args:
            test_file: 產出的測試檔案。
            plugin: 語言插件。

        Returns:
            UnitTestResult。
        """
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        test_file_path = self.test_dir / Path(test_file.path).name

        # 確保測試檔案已寫入
        if not test_file_path.is_file():
            test_file_path.write_text(test_file.content, encoding="utf-8")

        run_result = plugin.run_tests(
            test_file_path=test_file_path,
            work_dir=self.work_dir,
            timeout=self.timeout_sec,
            source_dirs=self.source_dirs,
        )

        # 寫入 log
        log_name = Path(test_file.path).stem
        log_path = self.logs_dir / f"{log_name}.log"
        log_path.write_text(
            f"exit_code: {run_result.exit_code}\n\n"
            f"stdout:\n{run_result.stdout}\n\n"
            f"stderr:\n{run_result.stderr}",
            encoding="utf-8",
        )

        # 先從完整 stdout 解析個別 test item（需要在截斷前）
        failure_reasons = _parse_failure_reasons(run_result.stdout)
        test_items = _parse_pytest_verbose_items(run_result.stdout, failure_reasons)

        # 解析 passed/failed/errored from stdout
        passed, failed, errored = _parse_test_summary(run_result.stdout)

        return UnitTestResult(
            test_file=test_file.path,
            total=passed + failed + errored,
            passed=passed,
            failed=failed,
            errored=errored,
            coverage_pct=run_result.coverage_pct,
            stdout=run_result.stdout[-2000:] if run_result.stdout else None,
            stderr=run_result.stderr[-1000:] if run_result.stderr else None,
            exit_code=run_result.exit_code,
            test_items=test_items,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VERBOSE_RE = re.compile(
    r"^(\S*::(\S+))\s+(PASSED|FAILED|ERROR|SKIPPED)",
    re.MULTILINE,
)

_STATUS_MAP: dict[str, TestItemStatus] = {
    "PASSED": TestItemStatus.PASSED,
    "FAILED": TestItemStatus.FAILED,
    "ERROR": TestItemStatus.ERROR,
    "SKIPPED": TestItemStatus.SKIPPED,
}


def _parse_pytest_verbose_items(
    stdout: str,
    failure_reasons: dict[str, str] | None = None,
) -> list[TestItemResult]:
    """從 pytest -v 輸出解析個別 test function 的結果。

    匹配格式如 ``test_file.py::test_name PASSED``。

    Args:
        stdout: pytest 標準輸出。
        failure_reasons: test_name → 錯誤訊息的 mapping。

    Returns:
        TestItemResult 清單。
    """
    if failure_reasons is None:
        failure_reasons = {}
    items: list[TestItemResult] = []
    for match in _VERBOSE_RE.finditer(stdout):
        test_name = match.group(2)  # 只取函式名
        status_str = match.group(3)
        items.append(
            TestItemResult(
                test_name=test_name,
                status=_STATUS_MAP[status_str],
                failure_reason=failure_reasons.get(test_name),
            )
        )
    return items


_FAILURE_REASON_RE = re.compile(
    r"^(?:FAILED|ERROR)\s+\S*::(\S+)\s+-\s+(.+)$",
    re.MULTILINE,
)

_ERROR_SECTION_RE = re.compile(
    r"_{2,}\s+ERROR at (?:setup|teardown) of (\S+)\s+_{2,}\n"
    r"(.*?)(?=\n_{2,}|\n={2,})",
    re.DOTALL,
)

_ERROR_LINE_RE = re.compile(r"^E\s+(.+)$", re.MULTILINE)


def _parse_failure_reasons(stdout: str) -> dict[str, str]:
    """從 pytest 輸出解析失敗與錯誤原因。

    優先從 short test summary（``FAILED path::test - reason``）解析，
    再從 ERRORS section（setup/teardown errors）補充缺漏。

    Args:
        stdout: pytest 標準輸出。

    Returns:
        {test_name: error_message} mapping。
    """
    reasons: dict[str, str] = {}

    # 1) short test summary: FAILED/ERROR path::test_name - reason
    for match in _FAILURE_REASON_RE.finditer(stdout):
        test_name = match.group(1)
        reason = match.group(2).strip()
        reasons[test_name] = reason

    # 2) ERRORS section: setup/teardown errors（補充 short summary 沒有的）
    for match in _ERROR_SECTION_RE.finditer(stdout):
        test_name = match.group(1)
        if test_name in reasons:
            continue
        block = match.group(2)
        e_lines = _ERROR_LINE_RE.findall(block)
        if e_lines:
            reasons[test_name] = e_lines[-1].strip()

    return reasons


def _parse_test_summary(stdout: str) -> tuple[int, int, int]:
    """從 test stdout 解析 passed/failed/error 數量。

    支援 pytest 格式（"X passed, Y failed"）。
    其他語言的格式需要擴充。

    Args:
        stdout: 測試標準輸出。

    Returns:
        (passed, failed, errored) 元組。
    """
    passed = failed = errored = 0

    match = re.search(r"(\d+) passed", stdout)
    if match:
        passed = int(match.group(1))

    match = re.search(r"(\d+) failed", stdout)
    if match:
        failed = int(match.group(1))

    match = re.search(r"(\d+) error", stdout)
    if match:
        errored = int(match.group(1))

    return passed, failed, errored
