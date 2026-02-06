"""C Language Plugin：處理 C 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（編譯 + 執行舊 C code → JSON stdout）
- 用 gcc + gcov 執行並收集 coverage
- 生成 test driver（用 golden values 作為 expected）
- 用 gcc 編譯執行 test
- gcc 檢查 build
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
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
Generate a standalone C program that captures behavioral output from the source code.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported headers):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- Create a main() function that calls the functions from the source
- Include necessary headers (#include "source.h" or #include "source.c")
- Use printf() to output results in JSON format
- For each function call, use descriptive keys like "FunctionName_scenario"
- Do NOT use generic keys like "result1", "test1", "output"
- Output format: printf("{{\\n");  then key-value pairs, then printf("}}\\n");
- Use proper JSON escaping for strings
- Compilable with: gcc -o golden golden.c source.c
- No markdown code fences, return raw C code only
"""

USER_TEST_GENERATION: str = """\
Generate a C test driver for behavioral validation.

New source files (after refactoring to Rust, but we test via C-compatible interface):
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
1. Create a test driver with main() that validates each golden output
2. Use assert() or custom test macros for assertions
3. Print test results: "PASS: test_name" or "FAIL: test_name - reason"
4. Return 0 if all tests pass, non-zero otherwise
5. Include necessary headers
6. For floating point comparisons, use epsilon tolerance
7. If a golden key has no corresponding function, skip with comment
8. No markdown code fences, return raw C code only
9. Compilable with: gcc -o test_runner test_driver.c
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class CPlugin(LanguagePlugin):
    """C 語言插件。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 C golden capture 程式。"""
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
        """編譯並執行 C 程式，收集 coverage（使用 gcov）。"""
        try:
            # 找到同目錄下的 .c 源檔案
            script_dir = script_path.parent
            source_files = list(script_dir.glob("*.c"))
            source_files = [f for f in source_files if f != script_path]

            # 編譯參數
            output_binary = script_path.with_suffix("")
            compile_cmd = [
                "gcc",
                "-fprofile-arcs",
                "-ftest-coverage",
                "-o",
                str(output_binary),
                str(script_path),
            ]
            compile_cmd.extend(str(f) for f in source_files)

            # 編譯
            compile_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
            )

            if compile_result.returncode != 0:
                return TestRunResult(
                    exit_code=compile_result.returncode,
                    stdout=compile_result.stdout,
                    stderr=f"Compilation failed:\n{compile_result.stderr}",
                )

            # 執行
            run_result = subprocess.run(
                [str(output_binary)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
            )

            # 解析 gcov coverage（如果有的話）
            coverage_pct = _parse_gcov_coverage(script_dir)

            return TestRunResult(
                exit_code=run_result.returncode,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
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
        """生成 C test driver。"""
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
        """編譯並執行 C test driver。"""
        try:
            # 找到同目錄下的 .c 源檔案（排除 test driver 本身）
            test_dir = test_file_path.parent
            source_files = list(test_dir.glob("*.c"))
            source_files = [f for f in source_files if f != test_file_path]

            # 編譯
            output_binary = test_file_path.with_suffix("")
            compile_cmd = [
                "gcc",
                "-fprofile-arcs",
                "-ftest-coverage",
                "-o",
                str(output_binary),
                str(test_file_path),
            ]
            compile_cmd.extend(str(f) for f in source_files)

            compile_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
            )

            if compile_result.returncode != 0:
                return TestRunResult(
                    exit_code=compile_result.returncode,
                    stdout=compile_result.stdout,
                    stderr=f"Compilation failed:\n{compile_result.stderr}",
                )

            # 執行測試
            run_result = subprocess.run(
                [str(output_binary)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
            )

            # 解析 coverage
            coverage_pct = _parse_gcov_coverage(test_dir)

            return TestRunResult(
                exit_code=run_result.returncode,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
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
        """用 gcc 檢查所有 C 檔案是否可編譯。"""
        # 找到所有 .c 檔案
        c_files = list(repo_dir.rglob("*.c"))
        if not c_files:
            return True, "No C files found"

        all_output = []
        all_success = True

        for c_file in c_files:
            try:
                # 使用 -fsyntax-only 只檢查語法
                result = subprocess.run(
                    ["gcc", "-fsyntax-only", str(c_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(repo_dir),
                )
                if result.returncode != 0:
                    all_success = False
                    all_output.append(f"{c_file.name}: {result.stderr}")
                else:
                    all_output.append(f"{c_file.name}: OK")
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT checking {c_file.name}"
            except Exception as exc:
                return False, f"Error checking {c_file.name}: {str(exc)[:200]}"

        return all_success, "\n".join(all_output)

    def parse_test_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> tuple[int, int, int, list[TestItemResult]]:
        """解析 C test driver 輸出。"""
        test_items = _parse_c_test_items(stdout)
        passed = sum(1 for t in test_items if t.status == TestItemStatus.PASSED)
        failed = sum(1 for t in test_items if t.status == TestItemStatus.FAILED)
        errored = 0

        # 如果 exit_code != 0 但沒有解析到任何測試結果，視為錯誤
        if exit_code != 0 and not test_items:
            errored = 1

        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 C 測試檔案的語法（使用 gcc -fsyntax-only）。"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())
            test_file = temp_dir / "test_syntax_check.c"
            test_file.write_text(test_content, encoding="utf-8")

            result = subprocess.run(
                ["gcc", "-fsyntax-only", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(temp_dir),
            )

            if result.returncode != 0:
                return False, result.stderr
            return True, ""

        except subprocess.TimeoutExpired:
            return False, "Syntax check timeout"
        except Exception as e:
            return False, str(e)
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def check_source_compilation(
        self,
        module_files: list[Path],
        work_dir: Path,
    ) -> tuple[bool, str]:
        """檢查 C 原始碼是否可編譯。"""
        try:
            if not module_files:
                return False, "No module files provided"

            errors = []
            for c_file in module_files:
                if c_file.suffix != ".c":
                    continue

                result = subprocess.run(
                    ["gcc", "-fsyntax-only", str(c_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(work_dir),
                )

                if result.returncode != 0:
                    errors.append(f"{c_file.name}: {result.stderr}")

            if errors:
                return False, "\n".join(errors)
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
                f"```c\n{source_code}\n```"
            )
        return source_code

    def generate_execution_artifacts(
        self,
        repo_dir: Path,
        output_dir: Path,
        language: str,
        llm_client: Any,
        script_path: Path | None = None,
        test_file_path: Path | None = None,
        source_dirs: list[str] | None = None,
        sandbox_base: str | None = None,
        local_base: Path | None = None,
    ) -> dict[str, Path]:
        """生成 Makefile 和 execution.sh"""
        artifacts = {}

        # 1. 用 LLM 生成或補充 Makefile
        makefile_path = output_dir / "Makefile"
        makefile_content = self._generate_makefile_with_llm(
            script_path=script_path,
            test_file_path=test_file_path,
            repo_dir=repo_dir,
            source_dirs=source_dirs,
            llm_client=llm_client,
        )
        makefile_path.write_text(makefile_content, encoding="utf-8")
        artifacts["requirements"] = makefile_path

        # 2. 用模板生成 execution.sh
        if script_path or test_file_path:
            sh_path = (
                output_dir / "execute_golden.sh"
                if script_path
                else output_dir / "execute_test.sh"
            )
            sh_content = self._generate_sh_with_template(
                script_path=script_path,
                test_file_path=test_file_path,
                repo_dir=repo_dir,
                source_dirs=source_dirs,
                output_dir=output_dir,
                sandbox_base=sandbox_base,
                local_base=local_base,
            )
            sh_path.write_text(sh_content, encoding="utf-8")
            sh_path.chmod(0o755)
            artifacts["execution_sh"] = sh_path

        return artifacts

    def _generate_makefile_with_llm(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        source_dirs: list[str] | None,
        llm_client: Any,
    ) -> str:
        """用 LLM 分析 #include 並生成 Makefile"""
        target_file = script_path or test_file_path
        if not target_file or not target_file.exists():
            return self._default_makefile()

        code_content = target_file.read_text(encoding="utf-8")

        # 檢查現有 Makefile
        existing_makefile = repo_dir / "Makefile"
        existing_content = ""
        if existing_makefile.exists():
            existing_content = existing_makefile.read_text(encoding="utf-8")

        prompt = f"""Analyze the following C code and generate a Makefile.

Code to analyze:
```c
{code_content}
```

Existing Makefile in repo (if any):
```
{existing_content if existing_content else "None"}
```

Source directories: {source_dirs or ["."]}

Task:
1. Extract all #include directives and identify required libraries
2. Generate appropriate -I (include path) flags for source_dirs
3. Generate -l flags for external libraries (e.g., -lm for math.h)
4. If existing Makefile exists, use it as base and enhance
5. Include targets: all, clean, golden_runner (or test_runner), coverage
6. Use gcc with -fprofile-arcs -ftest-coverage for coverage support

Output ONLY the Makefile content, no explanations."""

        makefile = llm_client.generate(prompt).strip()

        # 清理 LLM 輸出
        if makefile.startswith("```"):
            lines = makefile.split("\n")
            makefile = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        return makefile.strip() or self._default_makefile()

    def _default_makefile(self) -> str:
        """預設 Makefile"""
        return """CC = gcc
CFLAGS = -Wall -Wextra -g
COV_FLAGS = -fprofile-arcs -ftest-coverage

all: runner

runner: *.c
\t$(CC) $(CFLAGS) -o $@ $^

coverage: *.c
\t$(CC) $(CFLAGS) $(COV_FLAGS) -o runner $^
\t./runner
\tgcov *.c

clean:
\trm -f runner *.o *.gcda *.gcno *.gcov
"""

    def _generate_sh_with_template(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        source_dirs: list[str] | None,
        output_dir: Path,
        sandbox_base: str | None = None,
        local_base: Path | None = None,
    ) -> str:
        """用模板生成 execution.sh"""

        def to_sandbox_path(local_path: Path) -> str:
            """將本地路徑轉換為 sandbox 路徑。"""
            if sandbox_base and local_base:
                try:
                    rel = local_path.resolve().relative_to(local_base.resolve())
                    return f"{sandbox_base}/{rel}"
                except ValueError:
                    pass
            return str(local_path.resolve())

        repo_dir_str = to_sandbox_path(repo_dir)
        output_dir_str = to_sandbox_path(output_dir)

        # 建立 -I include flags
        include_flags = []
        if source_dirs:
            for src_dir in source_dirs:
                include_flags.append(f'-I"$REPO_DIR/{src_dir}"')
        include_flags_str = " ".join(include_flags) if include_flags else ""

        if script_path:
            script_str = to_sandbox_path(script_path)
            script_dir_str = to_sandbox_path(script_path.parent)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
SCRIPT_DIR="{script_dir_str}"
SCRIPT="{script_str}"

# Include flags
INCLUDE_FLAGS="{include_flags_str}"

# 1. Compile golden script
cd "$SCRIPT_DIR"
gcc -Wall $INCLUDE_FLAGS -o golden_runner "$SCRIPT" *.c 2>/dev/null || \\
gcc -Wall $INCLUDE_FLAGS -o golden_runner "$SCRIPT"

# 2. Execute
./golden_runner
"""
        elif test_file_path:
            test_str = to_sandbox_path(test_file_path)
            test_dir_str = to_sandbox_path(test_file_path.parent)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
TEST_DIR="{test_dir_str}"
TEST_FILE="{test_str}"

# Include flags
INCLUDE_FLAGS="{include_flags_str}"

# 1. Compile with coverage
cd "$TEST_DIR"
gcc -Wall -fprofile-arcs -ftest-coverage $INCLUDE_FLAGS \\
    -o test_runner "$TEST_FILE" *.c 2>/dev/null || \\
gcc -Wall -fprofile-arcs -ftest-coverage $INCLUDE_FLAGS \\
    -o test_runner "$TEST_FILE"

# 2. Execute tests
./test_runner

# 3. Generate coverage report
gcov *.c 2>/dev/null || true
"""
        else:
            return "#!/bin/bash\necho 'No script specified'\n"


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
    if script.startswith("```c"):
        script = script[len("```c") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _parse_gcov_coverage(work_dir: Path) -> float | None:
    """從 gcov 輸出解析 coverage 百分比。"""
    try:
        # 找到 .gcda 檔案
        gcda_files = list(work_dir.glob("*.gcda"))
        if not gcda_files:
            return None

        # 執行 gcov
        result = subprocess.run(
            ["gcov"] + [str(f) for f in gcda_files],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(work_dir),
        )

        # 解析輸出，格式如: "Lines executed:85.71% of 14"
        total_lines = 0
        executed_lines = 0
        for line in result.stdout.splitlines():
            match = re.search(r"Lines executed:([\d.]+)% of (\d+)", line)
            if match:
                pct = float(match.group(1))
                lines = int(match.group(2))
                executed_lines += int(pct * lines / 100)
                total_lines += lines

        if total_lines > 0:
            return round(executed_lines / total_lines * 100, 2)
        return None

    except Exception:
        return None


def _parse_c_test_items(stdout: str) -> list[TestItemResult]:
    """從 C test driver 輸出解析測試結果。

    預期格式:
    - "PASS: test_name"
    - "FAIL: test_name - reason"
    """
    items: list[TestItemResult] = []

    # 匹配 PASS: test_name
    pass_pattern = re.compile(r"^PASS:\s*(\S+)", re.MULTILINE)
    for match in pass_pattern.finditer(stdout):
        items.append(
            TestItemResult(
                test_name=match.group(1),
                status=TestItemStatus.PASSED,
                failure_reason=None,
            )
        )

    # 匹配 FAIL: test_name - reason
    fail_pattern = re.compile(r"^FAIL:\s*(\S+)\s*-?\s*(.*)?$", re.MULTILINE)
    for match in fail_pattern.finditer(stdout):
        items.append(
            TestItemResult(
                test_name=match.group(1),
                status=TestItemStatus.FAILED,
                failure_reason=match.group(2).strip() if match.group(2) else None,
            )
        )

    return items
