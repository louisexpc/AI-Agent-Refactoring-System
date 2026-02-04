"""Python Language Plugin：處理 Python 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（import + 呼叫 public API → JSON stdout）
- 用 coverage run 執行腳本
- 生成 pytest test file（用 golden values 作為 expected）
- 用 pytest + coverage 執行 test
- python -m py_compile 檢查 build
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from runner.test_gen.plugins import LanguagePlugin, TestRunResult

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

GOLDEN_SCRIPT_PROMPT: str = """\
You are a senior test engineer. Generate a standalone Python script that:
1. Imports all public functions/classes from the source files
2. Calls each public function with representative arguments
3. Prints ALL return values as a single JSON object to stdout

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}
Use this context to understand the types, classes and functions available.

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- The source module directories are already on PYTHONPATH. You can import
  source modules directly by their module name without any sys.path manipulation.
  Example: `from sensor import Sensor` or `from tire_pressure_monitoring import Alarm`.
  Do NOT use sys.path.insert(), os.path manipulation, or __file__-relative paths.
- The script must be self-contained and runnable with `python script.py`
- Use `from unittest.mock import patch` if mocking is needed
- For class methods, instantiate the class first
- Use DESCRIPTIVE keys in the results dict so we know what was tested.
  Format: "ClassName_methodName_scenario" or "functionName_scenario".
  Do NOT use generic keys like "result1", "test1", "output".
- Collect all results into a dict and print as JSON on the LAST line
- The LAST line must be: print(json.dumps(results, default=str))
- Do NOT include markdown code fences, return raw Python code only
- Do NOT print anything else to stdout
"""

CHARACTERIZATION_TEST_PROMPT: str = """\
You are a senior test engineer. Generate a complete pytest test file
that verifies the refactored code produces the same outputs as the original code.

New source files (after refactoring):
{file_sections}

Dependent source files (signatures):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Golden output (expected behavior from the original code):
{golden_output}

Requirements:
1. For each golden output key, find the corresponding function/class in the new code
   and assert it produces the same value
2. The source module directories are already on PYTHONPATH. You can import
   source modules directly by their module name without any sys.path manipulation.
   Example: `from sensor import Sensor` or `from tire_pressure_monitoring import Alarm`.
   Do NOT use sys.path.insert(), os.path manipulation, or __file__-relative paths.
3. Use pytest assertions (assert actual == expected)
4. For mocking, use `from unittest.mock import patch, MagicMock` (stdlib).
   Do NOT use the `mocker` fixture or `pytest-mock` — it is not installed.
5. Mock any side effects (file I/O, network, DB) as indicated in guidance
6. If a golden key has no corresponding function in the new code, skip it with
   a comment explaining why
7. Do NOT include markdown code fences, return raw Python code only
8. The test file must be self-contained and runnable with `pytest test_file.py`
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class PythonPlugin(LanguagePlugin):
    """Python 語言插件。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 Python golden capture 腳本。"""
        file_sections = self._build_file_sections(source_code, module_paths)

        prompt = GOLDEN_SCRIPT_PROMPT.format(
            file_sections=file_sections,
            dependency_info=dep_signatures or "No internal dependencies.",
            side_effects=_guidance_field(guidance, "side_effects"),
            mock_recommendations=_guidance_field(guidance, "mock_recommendations"),
            nondeterminism_notes=_guidance_field(guidance, "nondeterminism_notes"),
        )

        response = llm_client.generate(prompt)
        return _strip_code_fences(response)

    def run_with_coverage(
        self,
        script_path: Path,
        work_dir: Path,
        timeout: int,
        source_dirs: list[str] | None = None,
    ) -> TestRunResult:
        """用 coverage run 執行腳本。"""
        cov_data = script_path.with_suffix(".coverage")

        env = os.environ.copy()
        env["PYTHONPATH"] = _build_pythonpath(work_dir, source_dirs)

        try:
            result = subprocess.run(
                [
                    "coverage",
                    "run",
                    f"--data-file={cov_data}",
                    str(script_path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )
            coverage_pct = _read_coverage(cov_data)
            return TestRunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                coverage_pct=coverage_pct,
            )
        except subprocess.TimeoutExpired:
            return TestRunResult(exit_code=-1, stderr="TIMEOUT")
        except Exception as exc:
            return TestRunResult(exit_code=-1, stderr=str(exc)[:500])

    def generate_test_file(
        self,
        new_source_code: str,
        module_paths: list[str],
        golden_values: dict[str, Any],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 pytest characterization test file。"""
        file_sections = self._build_file_sections(new_source_code, module_paths)
        golden_str = json.dumps(golden_values, indent=2, default=str)

        prompt = CHARACTERIZATION_TEST_PROMPT.format(
            file_sections=file_sections,
            dependency_info=dep_signatures or "No internal dependencies.",
            side_effects=_guidance_field(guidance, "side_effects"),
            mock_recommendations=_guidance_field(guidance, "mock_recommendations"),
            nondeterminism_notes=_guidance_field(guidance, "nondeterminism_notes"),
            golden_output=golden_str,
        )

        response = llm_client.generate(prompt)
        return _strip_code_fences(response)

    def run_tests(
        self,
        test_file_path: Path,
        work_dir: Path,
        timeout: int,
        source_dirs: list[str] | None = None,
    ) -> TestRunResult:
        """用 pytest + coverage 執行 test file。"""
        # 寫入 conftest.py 確保 source_dirs 在 sys.path 最前面
        _write_conftest(test_file_path.parent, work_dir, source_dirs)

        cmd = [
            "python",
            "-m",
            "pytest",
            str(test_file_path),
            "-v",
            "--tb=short",
            "--no-header",
            f"--rootdir={work_dir}",
            "-o",
            "addopts=",
            f"--cov={work_dir}",
            "--cov-report=json",
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = _build_pythonpath(work_dir, source_dirs)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            coverage_pct = _parse_pytest_coverage(work_dir, result.stdout)

            return TestRunResult(
                exit_code=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                coverage_pct=coverage_pct,
            )
        except subprocess.TimeoutExpired:
            return TestRunResult(exit_code=-1, stderr="TIMEOUT")
        except Exception as exc:
            return TestRunResult(exit_code=-1, stderr=str(exc)[:500])

    def check_build(
        self,
        repo_dir: Path,
        timeout: int,
    ) -> tuple[bool, str]:
        """用 py_compile 檢查所有 .py 檔案。"""
        try:
            result = subprocess.run(
                ["python", "-m", "compileall", "-q", str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        except Exception as exc:
            return False, str(exc)[:500]

    def _build_file_sections(self, source_code: str, module_paths: list[str]) -> str:
        """將 source_code 包裝成帶路徑標記的區段。"""
        if len(module_paths) == 1:
            return (
                f"File: {module_paths[0]}\n"
                f"Directory: {str(Path(module_paths[0]).parent)}\n"
                f"Module name: {Path(module_paths[0]).stem}\n"
                f"```python\n{source_code}\n```"
            )
        return source_code  # 多檔時已經預先格式化


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_conftest(
    test_dir: Path,
    work_dir: Path,
    source_dirs: list[str] | None,
) -> None:
    """在測試目錄寫入 conftest.py，將 source_dirs 插入 sys.path 最前面。

    PYTHONPATH 優先順序低於 sys.path[0]（cwd），因此需要透過
    conftest.py 在 pytest import collection 前就把正確路徑插到最前面。

    Args:
        test_dir: 測試檔案所在目錄。
        work_dir: repo 根目錄。
        source_dirs: 原始碼目錄相對路徑。
    """
    if not source_dirs:
        return

    abs_dirs = []
    seen: set[str] = set()
    for d in source_dirs:
        abs_dir = str(work_dir / d)
        if abs_dir not in seen:
            seen.add(abs_dir)
            abs_dirs.append(abs_dir)

    if not abs_dirs:
        return

    paths_str = ", ".join(repr(d) for d in abs_dirs)
    conftest_path = test_dir / "conftest.py"
    conftest_path.write_text(
        f"import sys\nsys.path[:0] = [{paths_str}]\n",
        encoding="utf-8",
    )


def _build_pythonpath(
    work_dir: Path,
    source_dirs: list[str] | None = None,
) -> str:
    """建構 PYTHONPATH，包含 work_dir、source_dirs、既有 PYTHONPATH。

    Args:
        work_dir: repo 根目錄。
        source_dirs: 原始碼目錄相對路徑（如 ``Python/TirePressureMonitoringSystem``）。

    Returns:
        合併後的 PYTHONPATH 字串。
    """
    parts: list[str] = []

    # 1) source_dirs（最高優先）
    if source_dirs:
        seen: set[str] = set()
        for d in source_dirs:
            abs_dir = str(work_dir / d)
            if abs_dir not in seen:
                seen.add(abs_dir)
                parts.append(abs_dir)

    # 2) work_dir/Python（如果存在）
    python_subdir = work_dir / "Python"
    if python_subdir.is_dir():
        parts.append(str(python_subdir))

    # 3) work_dir
    parts.append(str(work_dir))

    # 4) 既有 PYTHONPATH
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)

    return ":".join(parts)


def _guidance_field(guidance: dict[str, Any] | None, key: str) -> str:
    """安全取出 guidance 欄位。"""
    if guidance is None:
        return "none"
    val = guidance.get(key)
    if val is None:
        return "none"
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else "none"
    return str(val)


def _strip_code_fences(text: str) -> str:
    """清除 LLM 回應中的 markdown code fence。"""
    script = text.strip()
    if script.startswith("```python"):
        script = script[len("```python") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _read_coverage(cov_data: Path) -> float | None:
    """從 coverage data file 讀取覆蓋率百分比。"""
    if not cov_data.exists():
        return None
    try:
        result = subprocess.run(
            ["coverage", "report", f"--data-file={cov_data}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in reversed(result.stdout.splitlines()):
            if "TOTAL" in line:
                parts = line.split()
                for part in reversed(parts):
                    if part.endswith("%"):
                        return float(part[:-1])
        return None
    except Exception:
        return None


def _parse_pytest_coverage(work_dir: Path, stdout: str) -> float | None:
    """從 pytest-cov 輸出或 coverage.json 解析覆蓋率。"""
    cov_json = work_dir / "coverage.json"
    if cov_json.is_file():
        try:
            data = json.loads(cov_json.read_text(encoding="utf-8"))
            pct = data.get("totals", {}).get("percent_covered")
            if pct is not None:
                return round(float(pct), 2)
        except (json.JSONDecodeError, KeyError):
            pass

    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    if match:
        return float(match.group(1))

    return None
