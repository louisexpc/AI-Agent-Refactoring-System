"""Phase 5b：執行 emitted test files 並收集結果。

將 TestCodeEmitter 產出的測試檔案實際跑起來（pytest），
收集 pass/fail 數量與 coverage 數據回寫到 TestReport。
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.test_types import EmittedTestFile, UnitTestResult


@dataclass
class TestRunner:
    """執行 emitted test files 並收集結果。

    使用 subprocess 跑 pytest，解析輸出取得
    pass/fail 數量和 coverage 百分比。

    Args:
        repo_dir: 被測程式碼的 repo 目錄（pytest cwd）。
        test_dir: emitted 測試檔案所在目錄。
        logs_dir: 執行日誌輸出目錄。
        timeout_sec: 單檔測試超時秒數。
        collect_coverage: 是否收集 coverage。
    """

    repo_dir: Path
    test_dir: Path
    logs_dir: Path
    timeout_sec: int = 60
    collect_coverage: bool = True

    def run(self, emitted_files: list[EmittedTestFile]) -> list[UnitTestResult]:
        """執行所有 emitted test files。

        Args:
            emitted_files: 產出的測試檔案清單。

        Returns:
            每個測試檔案的執行結果。
        """
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        results: list[UnitTestResult] = []

        for emitted in emitted_files:
            result = self._run_one(emitted)
            results.append(result)

        return results

    def _run_one(self, emitted: EmittedTestFile) -> UnitTestResult:
        """執行單一測試檔案。

        Args:
            emitted: 測試檔案。

        Returns:
            UnitTestResult。
        """
        test_file_path = self.test_dir / Path(emitted.path).name
        if not test_file_path.is_file():
            return UnitTestResult(
                test_file=emitted.path,
                stderr=f"Test file not found: {test_file_path}",
                exit_code=-1,
            )

        # 組裝 pytest 指令
        cmd = [
            "python",
            "-m",
            "pytest",
            str(test_file_path),
            "-v",
            "--tb=short",
            "--no-header",
            f"--rootdir={self.repo_dir}",
            "-o",
            "addopts=",
        ]
        if self.collect_coverage:
            # 用 pytest-cov 收集 coverage，對 repo_dir 量測
            cmd.extend(
                [
                    f"--cov={self.repo_dir}",
                    "--cov-report=json",
                ]
            )

        log_name = Path(emitted.path).stem

        # 設定 PYTHONPATH 讓測試檔能 import 來源模組
        import os

        env = os.environ.copy()
        source_dir = str(self.repo_dir / Path(emitted.source_file).parent)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{source_dir}:{existing}" if existing else source_dir

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                cwd=str(self.repo_dir),
                env=env,
            )

            # 寫入日誌
            log_path = self.logs_dir / f"{log_name}.log"
            log_path.write_text(
                f"cmd: {' '.join(cmd)}\n\n"
                f"exit_code: {result.returncode}\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}",
                encoding="utf-8",
            )

            # 解析 pytest 輸出
            passed, failed, errored = self._parse_pytest_summary(result.stdout)
            coverage_pct = self._parse_coverage(result.stdout)

            return UnitTestResult(
                test_file=emitted.path,
                total=passed + failed + errored,
                passed=passed,
                failed=failed,
                errored=errored,
                coverage_pct=coverage_pct,
                stdout=result.stdout[-2000:] if result.stdout else None,
                stderr=result.stderr[-1000:] if result.stderr else None,
                exit_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            return UnitTestResult(
                test_file=emitted.path,
                stderr="TIMEOUT",
                exit_code=-1,
            )
        except Exception as exc:
            return UnitTestResult(
                test_file=emitted.path,
                stderr=str(exc)[:500],
                exit_code=-1,
            )

    def _parse_pytest_summary(self, stdout: str) -> tuple[int, int, int]:
        """從 pytest stdout 解析 passed/failed/error 數量。

        Args:
            stdout: pytest 標準輸出。

        Returns:
            (passed, failed, errored) 元組。
        """
        # pytest summary 格式: "X passed, Y failed, Z error"
        passed = 0
        failed = 0
        errored = 0

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

    def _parse_coverage(self, stdout: str) -> float | None:
        """從 pytest-cov 輸出解析覆蓋率。

        優先讀 coverage.json，fallback 用 regex 解析 TOTAL 行。

        Args:
            stdout: pytest 標準輸出。

        Returns:
            覆蓋率百分比或 None。
        """
        # 嘗試讀 coverage.json（pytest-cov 產出）
        cov_json = self.repo_dir / "coverage.json"
        if cov_json.is_file():
            try:
                data = json.loads(cov_json.read_text(encoding="utf-8"))
                pct = data.get("totals", {}).get("percent_covered")
                if pct is not None:
                    return round(float(pct), 2)
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: 從 stdout 解析 TOTAL 行
        # 格式: "TOTAL    xxx    xxx    xx%"
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
        if match:
            return float(match.group(1))

        return None
