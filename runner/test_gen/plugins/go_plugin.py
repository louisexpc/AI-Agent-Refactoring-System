"""Go Language Plugin：處理 Go 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（main package + 呼叫 public API → JSON stdout）
- 用 go run + coverage 執行腳本
- 生成 Go test file（用 golden values 作為 expected）
- 用 go test + coverage 執行 test
- go build 檢查 build
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from runner.test_gen.plugins import LanguagePlugin, TestRunResult
from runner.test_gen.system_prompts import (
    SYSTEM_GOLDEN_SCRIPT,
    SYSTEM_TEST_GENERATION,
)
from shared.test_types import TestItemResult, TestItemStatus

# ---------------------------------------------------------------------------
# User Prompt Templates (Task-specific)
# ---------------------------------------------------------------------------

USER_GOLDEN_SCRIPT: str = """\
Generate a standalone Go program (main package) that captures behavioral output.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- Package main with main() function
- Import the source package (e.g., "leaderboard")
- Import "encoding/json", "fmt", "os" for JSON output
- For struct methods, instantiate the struct first
- Use descriptive keys such as "TypeName_MethodName_scenario"
    or "FunctionName_scenario"
- Do NOT use generic keys like "result1", "test1", "output"
- Collect all results into map[string]interface{} and marshal
    them to JSON
- Print ONLY JSON output to stdout (use os.Stdout)
- No markdown code fences, return raw Go code only
- Runnable with: go run script.go
"""

USER_TEST_GENERATION: str = """\
Generate a complete Go test file for behavioral validation.

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
1. Match each golden output key to corresponding function/type
2. CRITICAL: Use the exact package name as the source.
    Example: "package leaderboard", NOT "package leaderboard_test"
3. Do NOT import source package - test in same package as source
4. Import only necessary packages: "testing", "reflect", and standard library
   CRITICAL: Do NOT import unused packages - Go treats unused imports as errors
5. Use testing.T methods (t.Errorf, t.Fatalf) for assertions
6. For mocking: standard Go techniques (interfaces, function variables)
7. Mock side effects (I/O, network, DB) as indicated in guidance
8. If golden key has no corresponding function, skip with explanatory comment
9. No markdown code fences, return raw Go code only
10. Runnable with: go test
11. Test functions: Test<Name> following Go conventions
12. Complex types: use reflect.DeepEqual or custom comparison
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class GoPlugin(LanguagePlugin):
    """Go 語言插件。"""

    def _setup_go_env(self) -> dict[str, str]:
        """設置 Go 執行環境變數（加入 Go binary 到 PATH）。"""
        env = os.environ.copy()
        # 加入常見的 Go 安裝路徑到 PATH
        go_paths = [
            os.path.expanduser("~/go/bin"),
            "/usr/local/go/bin",
            "/home/yoyo/go/bin",  # WSL specific
        ]
        existing_path = env.get("PATH", "")
        for go_path in go_paths:
            if os.path.exists(go_path) and go_path not in existing_path:
                env["PATH"] = f"{go_path}:{existing_path}"
                break
        return env

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 Go golden capture 腳本（main package）。"""
        file_sections = self._build_file_sections(source_code, module_paths)

        prompt = USER_GOLDEN_SCRIPT.format(
            file_sections=file_sections,
            dependency_info=dep_signatures or "No internal dependencies.",
            side_effects=_guidance_field(guidance, "side_effects"),
            mock_recommendations=_guidance_field(guidance, "mock_recommendations"),
            nondeterminism_notes=_guidance_field(guidance, "nondeterminism_notes"),
        )

        response = llm_client.generate(prompt, system_override=SYSTEM_GOLDEN_SCRIPT)
        return _strip_code_fences(response)

    def run_with_coverage(
        self,
        script_path: Path,
        work_dir: Path,
        timeout: int,
        source_dirs: list[str] | None = None,
    ) -> TestRunResult:
        """用 go run 執行腳本並收集 coverage。"""
        env = self._setup_go_env()

        try:
            # 先編譯以檢查語法
            compile_result = subprocess.run(
                ["go", "build", "-o", "/dev/null", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )
            if compile_result.returncode != 0:
                return TestRunResult(
                    exit_code=compile_result.returncode,
                    stdout=compile_result.stdout,
                    stderr=compile_result.stderr,
                )

            # 執行腳本
            result = subprocess.run(
                ["go", "run", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # Go coverage 需要在 test 環境中，暫時不支援 script coverage
            # 如果需要，可以將 script 轉換為 test 並使用 go test -cover
            return TestRunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                coverage_pct=None,  # Script coverage not supported yet
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
        """生成 Go test file。"""
        file_sections = self._build_file_sections(new_source_code, module_paths)
        golden_str = json.dumps(golden_values, indent=2, default=str)

        prompt = USER_TEST_GENERATION.format(
            file_sections=file_sections,
            dependency_info=dep_signatures or "No internal dependencies.",
            side_effects=_guidance_field(guidance, "side_effects"),
            mock_recommendations=_guidance_field(guidance, "mock_recommendations"),
            nondeterminism_notes=_guidance_field(guidance, "nondeterminism_notes"),
            golden_output=golden_str,
        )

        response = llm_client.generate(prompt, system_override=SYSTEM_TEST_GENERATION)
        return _strip_code_fences(response)

    def run_tests(
        self,
        test_file_path: Path,
        work_dir: Path,
        timeout: int,
        source_dirs: list[str] | None = None,
    ) -> TestRunResult:
        """用 go test + coverage 執行 test file。

        Go 測試需要和原始碼在同一個 package 目錄下。
        我們將測試檔案複製到 source_dirs[0]（原始碼目錄）並在那裡執行測試。
        """
        env = self._setup_go_env()

        # 找到原始碼目錄（第一個 source_dir）
        if not source_dirs or len(source_dirs) == 0:
            return TestRunResult(
                exit_code=-1,
                stderr="No source_dirs provided for Go test execution",
            )

        # source_dirs 包含相對路徑，需要轉換為絕對路徑
        source_dir = work_dir / source_dirs[0]
        if not source_dir.exists():
            return TestRunResult(
                exit_code=-1,
                stderr=f"Source directory not found: {source_dir}",
            )

        # 將測試檔案複製到原始碼目錄
        test_file_name = test_file_path.name
        target_test_path = source_dir / test_file_name

        try:
            import shutil

            shutil.copy2(test_file_path, target_test_path)
        except Exception as exc:
            return TestRunResult(
                exit_code=-1,
                stderr=f"Failed to copy test file: {exc}",
            )

        # 在原始碼目錄執行測試（不指定檔案名，讓 Go 自動發現所有測試）
        cmd = [
            "go",
            "test",
            "-v",
            "-cover",
            "-coverprofile=coverage.out",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(source_dir),
                env=env,
            )

            # 解析 coverage
            coverage_pct = _parse_go_coverage(source_dir, result.stdout)

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
        """用 go build 檢查所有 Go 檔案。"""
        env = self._setup_go_env()

        # 找到所有包含 .go 檔案的目錄
        go_dirs = set()
        for go_file in repo_dir.rglob("*.go"):
            # 排除 vendor 和 test 檔案
            if "vendor" not in go_file.parts:
                go_dirs.add(go_file.parent)

        if not go_dirs:
            return True, "No Go files found"

        # 對每個目錄執行 go build
        all_success = True
        all_output = []

        for go_dir in go_dirs:
            try:
                result = subprocess.run(
                    ["go", "build", "."],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(go_dir),
                    env=env,
                )
                all_output.append(
                    (
                        f"Dir: {go_dir.relative_to(repo_dir)}\n"
                        f"{result.stdout}{result.stderr}"
                    )
                )
                if result.returncode != 0:
                    all_success = False
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT in {go_dir}"
            except Exception as exc:
                return False, (f"Error in {go_dir}: " f"{str(exc)[:500]}")

        return all_success, "\n".join(all_output)

    def parse_test_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> tuple[int, int, int, list[TestItemResult]]:
        """解析 go test 測試輸出。"""
        test_items = _parse_go_test_items(stdout)
        passed, failed, errored = _parse_go_test_summary(stdout, exit_code)
        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 Go 測試檔案的語法。

        建立臨時目錄和 go.mod，建立空的原始碼檔案，用 go build 檢查測試語法。

        Args:
            test_content: 測試檔案內容。

        Returns:
            (成功, 錯誤訊息) 元組。
        """
        import shutil
        import tempfile

        temp_dir = None
        try:
            # 建立臨時目錄
            temp_dir = Path(tempfile.mkdtemp())

            # 提取 package 名稱
            package_name = self._extract_package_name(test_content)

            # 寫入 go.mod
            go_mod_path = temp_dir / "go.mod"
            go_mod_path.write_text(
                f"module temptest/{package_name}\n\ngo 1.21\n",
                encoding="utf-8",
            )

            # 寫入一個空的原始碼檔案（讓 go build 能夠編譯測試）
            stub_file_path = temp_dir / f"{package_name}.go"
            stub_file_path.write_text(
                f"package {package_name}\n\n// Stub file for testing\n",
                encoding="utf-8",
            )

            # 寫入測試檔案
            test_file_path = temp_dir / f"{package_name}_test.go"
            test_file_path.write_text(test_content, encoding="utf-8")

            # 設置環境變數
            env = self._setup_go_env()

            # 執行 go build（建置整個 package 包含測試）
            result = subprocess.run(
                ["go", "build", "."],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(temp_dir),
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                return False, error_msg
            return True, ""

        except subprocess.TimeoutExpired:
            return False, "Syntax check timeout"
        except Exception as e:
            return False, str(e)
        finally:
            # 清理臨時目錄
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def check_source_compilation(
        self,
        module_files: list[Path],
        work_dir: Path,
    ) -> tuple[bool, str]:
        """檢查 Go 原始碼是否可編譯。

        在 work_dir 中執行 go build，檢查是否有編譯錯誤。

        Args:
            module_files: 模組檔案路徑清單（絕對路徑）。
            work_dir: 工作目錄（refactored repo root）。

        Returns:
            (success, error_output) 元組。
        """
        try:
            # 取得檔案所在目錄（假設所有檔案在同一個 package 目錄）
            if not module_files:
                return False, "No module files provided"

            # 取得第一個檔案的目錄作為 package 目錄
            package_dir = module_files[0].parent

            # 設置環境變數
            env = self._setup_go_env()

            # 執行 go build（在 package 目錄下）
            result = subprocess.run(
                ["go", "build", "."],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(package_dir),
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                return False, error_msg

            return True, ""

        except subprocess.TimeoutExpired:
            return False, "Compilation check timeout"
        except Exception as e:
            return False, f"Compilation check error: {str(e)}"

    def _build_file_sections(self, source_code: str, module_paths: list[str]) -> str:
        """將 source_code 包裝成帶路徑標記的區段。"""
        if len(module_paths) == 1:
            return (
                f"File: {module_paths[0]}\n"
                f"Directory: {str(Path(module_paths[0]).parent)}\n"
                f"Package: {self._extract_package_name(source_code)}\n"
                f"```go\n{source_code}\n```"
            )
        return source_code  # 多檔時已經預先格式化

    def _extract_package_name(self, source_code: str) -> str:
        """從 Go 原始碼提取 package 名稱。"""
        match = re.search(r"^\s*package\s+(\w+)", source_code, re.MULTILINE)
        if match:
            return match.group(1)
        return "main"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    if script.startswith("```go"):
        script = script[len("```go") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _parse_go_coverage(test_dir: Path, stdout: str) -> float | None:
    """從 go test 輸出解析 coverage。

    Go test -cover 輸出格式：
    coverage: 85.7% of statements
    """
    # 從 stdout 解析
    match = re.search(r"coverage:\s+([\d.]+)%", stdout)
    if match:
        return float(match.group(1))

    # 從 coverage.out 檔案解析（如果存在）
    coverage_file = test_dir / "coverage.out"
    if coverage_file.exists():
        try:
            # 設置環境變數
            env = os.environ.copy()
            go_paths = [
                os.path.expanduser("~/go/bin"),
                "/usr/local/go/bin",
                "/home/yoyo/go/bin",
            ]
            existing_path = env.get("PATH", "")
            for go_path in go_paths:
                if os.path.exists(go_path) and go_path not in existing_path:
                    env["PATH"] = f"{go_path}:{existing_path}"
                    break

            # 使用 go tool cover 解析
            result = subprocess.run(
                ["go", "tool", "cover", "-func=coverage.out"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(test_dir),
                env=env,
            )
            # 輸出格式最後一行：total:  (statements) 85.7%
            for line in reversed(result.stdout.splitlines()):
                if "total:" in line.lower():
                    match = re.search(r"([\d.]+)%", line)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Go Test Output Parsing Helpers
# ---------------------------------------------------------------------------


def _parse_go_test_items(stdout: str) -> list[TestItemResult]:
    """從 go test -v 輸出解析個別 test function 的結果。

    Go test 輸出格式：
    === RUN   TestLeaderboard
    === RUN   TestLeaderboard/TestNewRaceInitialization
    --- PASS: TestLeaderboard/TestNewRaceInitialization (0.00s)
    --- PASS: TestLeaderboard (0.00s)

    Args:
        stdout: go test 標準輸出。

    Returns:
        TestItemResult 清單。
    """
    items: list[TestItemResult] = []
    # 匹配 --- PASS/FAIL: TestName (duration)
    pattern = re.compile(r"^\s*---\s+(PASS|FAIL|SKIP):\s+(\S+)", re.MULTILINE)

    for match in pattern.finditer(stdout):
        status_str = match.group(1)
        test_name = match.group(2)

        # 將狀態映射到 TestItemStatus
        if status_str == "PASS":
            status = TestItemStatus.PASSED
        elif status_str == "FAIL":
            status = TestItemStatus.FAILED
        elif status_str == "SKIP":
            status = TestItemStatus.SKIPPED
        else:
            status = TestItemStatus.ERROR

        items.append(
            TestItemResult(
                test_name=test_name,
                status=status,
                failure_reason=None,  # Go test 預設不提供詳細失敗原因
            )
        )

    return items


def _parse_go_test_summary(stdout: str, exit_code: int) -> tuple[int, int, int]:
    """從 go test stdout 解析 passed/failed/error 數量。

    Go test 格式：
    - 每個測試會輸出 PASS 或 FAIL
    - 最後會有 PASS 或 FAIL 總結

    Args:
        stdout: 測試標準輸出。
        exit_code: 測試結束碼。

    Returns:
        (passed, failed, errored) 元組。
    """
    passed = 0
    failed = 0
    errored = 0

    # 計算 PASS 的測試
    passed = len(re.findall(r"^\s*---\s+PASS:", stdout, re.MULTILINE))

    # 計算 FAIL 的測試
    failed = len(re.findall(r"^\s*---\s+FAIL:", stdout, re.MULTILINE))

    # 如果 exit_code != 0 但沒有 FAIL，可能是 build error 或其他錯誤
    if exit_code != 0 and failed == 0 and passed == 0:
        errored = 1

    return passed, failed, errored
