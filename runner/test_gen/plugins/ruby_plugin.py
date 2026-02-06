"""Ruby Language Plugin：處理 Ruby 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（require + 呼叫 public API → JSON stdout）
- 用 ruby + simplecov 執行腳本
- 生成 RSpec/Minitest test file（用 golden values 作為 expected）
- 用 rspec/minitest + simplecov 執行 test
- ruby -c 檢查語法
"""

from __future__ import annotations

import json
import os
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
Generate a standalone Ruby script that captures behavioral output.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- Use `require_relative` or `require` to import the source module
- The script must be self-contained and runnable with `ruby script.rb`
- For class methods, instantiate the class first
- Use DESCRIPTIVE keys in the results hash so we know what was tested.
  Format: "ClassName_methodName_scenario" or "functionName_scenario".
  Do NOT use generic keys like "result1", "test1", "output".
- Collect all results into a Hash and print as JSON on the LAST line
- The LAST line must be: puts JSON.dump(results)
- Do NOT include markdown code fences, return raw Ruby code only
- Do NOT print anything else to stdout
- Add `require 'json'` at the top
"""

USER_TEST_GENERATION: str = """\
Generate a complete RSpec test file for behavioral validation.

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
2. Use `require_relative` to import the source module
3. Use RSpec expectations (expect(actual).to eq(expected))
4. For mocking, use RSpec mocks or allow/receive
5. Mock any side effects (file I/O, network, DB) as indicated in guidance
6. If a golden key has no corresponding function in the new code, skip it with
   a comment explaining why
7. Do NOT include markdown code fences, return raw Ruby code only
8. The test file must be self-contained and runnable with `rspec test_file.rb`
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class RubyPlugin(LanguagePlugin):
    """Ruby 語言插件。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 Ruby golden capture 腳本。"""
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
        """用 ruby 執行腳本，收集 coverage（使用 simplecov）。"""
        env = os.environ.copy()
        env["RUBYLIB"] = _build_rubylib(work_dir, source_dirs)

        try:
            result = subprocess.run(
                ["ruby", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # 解析 simplecov coverage（如果有）
            coverage_pct = _parse_simplecov_coverage(work_dir)

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
        """生成 RSpec characterization test file。"""
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
        """用 rspec 執行 test file。"""
        env = os.environ.copy()
        env["RUBYLIB"] = _build_rubylib(work_dir, source_dirs)

        try:
            # 嘗試用 rspec，失敗則用 ruby 直接執行
            result = subprocess.run(
                [
                    "rspec",
                    str(test_file_path),
                    "--format",
                    "documentation",
                    "--format",
                    "json",
                    "--out",
                    str(work_dir / "rspec_results.json"),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # 解析 coverage
            coverage_pct = _parse_simplecov_coverage(work_dir)

            return TestRunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                coverage_pct=coverage_pct,
            )
        except FileNotFoundError:
            # rspec 不存在，嘗試用 ruby 直接執行（minitest）
            try:
                result = subprocess.run(
                    ["ruby", str(test_file_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(work_dir),
                    env=env,
                )
                return TestRunResult(
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    coverage_pct=None,
                )
            except Exception as exc:
                return TestRunResult(exit_code=-1, stderr=str(exc)[:500])
        except subprocess.TimeoutExpired:
            return TestRunResult(exit_code=-1, stderr="TIMEOUT")
        except Exception as exc:
            return TestRunResult(exit_code=-1, stderr=str(exc)[:500])

    def check_build(
        self,
        repo_dir: Path,
        timeout: int,
    ) -> tuple[bool, str]:
        """用 ruby -c 檢查所有 .rb 檔案語法。"""
        rb_files = list(repo_dir.rglob("*.rb"))
        if not rb_files:
            return True, "No Ruby files found"

        all_output = []
        all_success = True

        for rb_file in rb_files:
            try:
                result = subprocess.run(
                    ["ruby", "-c", str(rb_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(repo_dir),
                )
                if result.returncode != 0:
                    all_success = False
                    all_output.append(f"{rb_file.name}: {result.stderr}")
                else:
                    all_output.append(f"{rb_file.name}: Syntax OK")
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT checking {rb_file.name}"
            except Exception as exc:
                return False, f"Error checking {rb_file.name}: {str(exc)[:200]}"

        return all_success, "\n".join(all_output)

    def parse_test_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> tuple[int, int, int, list[TestItemResult]]:
        """解析 RSpec/Minitest 測試輸出。"""
        test_items = _parse_rspec_items(stdout)
        passed, failed, errored = _parse_rspec_summary(stdout)

        # 如果沒有解析到結果，嘗試 minitest 格式
        if passed == 0 and failed == 0 and errored == 0:
            passed, failed, errored = _parse_minitest_summary(stdout)
            if not test_items:
                test_items = _parse_minitest_items(stdout)

        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 Ruby 測試檔案的語法。"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())
            test_file = temp_dir / "test_syntax_check.rb"
            test_file.write_text(test_content, encoding="utf-8")

            result = subprocess.run(
                ["ruby", "-c", str(test_file)],
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
        """檢查 Ruby 原始碼語法。"""
        try:
            if not module_files:
                return False, "No module files provided"

            errors = []
            for rb_file in module_files:
                if rb_file.suffix != ".rb":
                    continue

                result = subprocess.run(
                    ["ruby", "-c", str(rb_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(work_dir),
                )

                if result.returncode != 0:
                    errors.append(f"{rb_file.name}: {result.stderr}")

            if errors:
                return False, "\n".join(errors)
            return True, ""

        except subprocess.TimeoutExpired:
            return False, "Syntax check timeout"
        except Exception as e:
            return False, f"Syntax check error: {str(e)}"

    def _build_file_sections(self, source_code: str, module_paths: list[str]) -> str:
        """將 source_code 包裝成帶路徑標記的區段。"""
        if len(module_paths) == 1:
            return (
                f"File: {module_paths[0]}\n"
                f"Directory: {str(Path(module_paths[0]).parent)}\n"
                f"Module name: {Path(module_paths[0]).stem}\n"
                f"```ruby\n{source_code}\n```"
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
        """生成 Gemfile 和 execution.sh"""
        artifacts = {}

        # 1. 用 LLM 生成 Gemfile
        gemfile_path = output_dir / "Gemfile"
        gemfile_content = self._generate_gemfile_with_llm(
            script_path=script_path,
            test_file_path=test_file_path,
            repo_dir=repo_dir,
            llm_client=llm_client,
        )
        gemfile_path.write_text(gemfile_content, encoding="utf-8")
        artifacts["requirements"] = gemfile_path

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

    def _generate_gemfile_with_llm(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        llm_client: Any,
    ) -> str:
        """用 LLM 分析 require 並生成 Gemfile"""
        target_file = script_path or test_file_path
        if not target_file or not target_file.exists():
            return self._default_gemfile()

        code_content = target_file.read_text(encoding="utf-8")

        # 檢查現有 Gemfile
        existing_gemfile = repo_dir / "Gemfile"
        existing_content = ""
        if existing_gemfile.exists():
            existing_content = existing_gemfile.read_text(encoding="utf-8")

        prompt = f"""Analyze the following Ruby code and generate a Gemfile.

Code to analyze:
```ruby
{code_content}
```

Existing Gemfile in repo (if any):
```
{existing_content if existing_content else "None"}
```

Task:
1. Extract all `require` statements and identify required gems
2. If existing Gemfile exists, use it as base and add any missing gems
3. If no existing Gemfile, generate from scratch
4. Always include rspec for testing
5. Always include simplecov for coverage
6. Always include json (stdlib, but explicit is good)

Output ONLY the Gemfile content, no explanations."""

        gemfile = llm_client.generate(prompt).strip()

        # 清理 LLM 輸出
        if gemfile.startswith("```"):
            lines = gemfile.split("\n")
            gemfile = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        return gemfile.strip() or self._default_gemfile()

    def _default_gemfile(self) -> str:
        """預設 Gemfile"""
        return """source 'https://rubygems.org'

gem 'json'
gem 'rspec', '~> 3.0'
gem 'simplecov', require: false
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
        gemfile_str = to_sandbox_path(output_dir / "Gemfile")

        # 建立 RUBYLIB
        rubylib_parts = []
        if source_dirs:
            for src_dir in source_dirs:
                rubylib_parts.append(f'"$REPO_DIR/{src_dir}"')
        rubylib_str = ":".join(rubylib_parts) if rubylib_parts else ""

        if script_path:
            script_str = to_sandbox_path(script_path)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
GEMFILE="{gemfile_str}"
SCRIPT="{script_str}"

# 1. Install dependencies
cd "$OUTPUT_DIR"
export BUNDLE_GEMFILE="$GEMFILE"
bundle install --path vendor/bundle

# 2. Set up RUBYLIB
export RUBYLIB="{rubylib_str}${{RUBYLIB:+:$RUBYLIB}}"

# 3. Execute golden script
cd "$REPO_DIR"
bundle exec ruby "$SCRIPT"
"""
        elif test_file_path:
            test_str = to_sandbox_path(test_file_path)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
GEMFILE="{gemfile_str}"
TEST_FILE="{test_str}"

# 1. Install dependencies
cd "$OUTPUT_DIR"
export BUNDLE_GEMFILE="$GEMFILE"
bundle install --path vendor/bundle

# 2. Set up RUBYLIB
export RUBYLIB="{rubylib_str}${{RUBYLIB:+:$RUBYLIB}}"

# 3. Execute tests with coverage
cd "$REPO_DIR"
bundle exec rspec "$TEST_FILE" --format documentation
"""
        else:
            return "#!/bin/bash\necho 'No script specified'\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_rubylib(
    work_dir: Path,
    source_dirs: list[str] | None = None,
) -> str:
    """建構 RUBYLIB 環境變數。"""
    parts: list[str] = []

    if source_dirs:
        seen: set[str] = set()
        for d in source_dirs:
            abs_dir = str(work_dir / d)
            if abs_dir not in seen:
                seen.add(abs_dir)
                parts.append(abs_dir)

    parts.append(str(work_dir))

    existing = os.environ.get("RUBYLIB", "")
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
    if script.startswith("```ruby"):
        script = script[len("```ruby") :].strip()
    if script.startswith("```rb"):
        script = script[len("```rb") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _parse_simplecov_coverage(work_dir: Path) -> float | None:
    """從 simplecov 輸出解析 coverage。"""
    # simplecov 預設輸出到 coverage/.resultset.json
    resultset = work_dir / "coverage" / ".resultset.json"
    if not resultset.exists():
        return None

    try:
        data = json.loads(resultset.read_text(encoding="utf-8"))
        # simplecov 格式：{"RSpec": {"coverage": {...}, "timestamp": ...}}
        for _name, result in data.items():
            if "coverage" in result:
                coverage_data = result["coverage"]
                total_lines = 0
                covered_lines = 0
                for _file, lines in coverage_data.items():
                    if isinstance(lines, dict):
                        lines = lines.get("lines", [])
                    for line in lines:
                        if line is not None:
                            total_lines += 1
                            if line > 0:
                                covered_lines += 1
                if total_lines > 0:
                    return round(covered_lines / total_lines * 100, 2)
        return None
    except Exception:
        return None


def _parse_rspec_items(stdout: str) -> list[TestItemResult]:
    """從 RSpec 輸出解析個別測試結果。"""
    items: list[TestItemResult] = []

    # RSpec documentation format: "  test name"
    # 後面跟著 (FAILED - 1) 或什麼都沒有（表示 pass）
    lines = stdout.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 檢查是否是測試行
        if "(FAILED" in line:
            # 移除 (FAILED - N) 部分
            match = re.match(r"(.+?)\s*\(FAILED", line)
            if match:
                test_name = match.group(1).strip()
                items.append(
                    TestItemResult(
                        test_name=test_name,
                        status=TestItemStatus.FAILED,
                        failure_reason=None,
                    )
                )
        elif line and not line.startswith("#") and not line.startswith("Finished"):
            # 可能是通過的測試（RSpec documentation format）
            if re.match(r"^[a-zA-Z]", line) and "example" not in line.lower():
                items.append(
                    TestItemResult(
                        test_name=line,
                        status=TestItemStatus.PASSED,
                        failure_reason=None,
                    )
                )

    return items


def _parse_rspec_summary(stdout: str) -> tuple[int, int, int]:
    """從 RSpec 輸出解析 summary。"""
    passed = failed = errored = 0

    # RSpec format: "X examples, Y failures, Z errors"
    match = re.search(r"(\d+)\s+examples?,\s+(\d+)\s+failures?", stdout)
    if match:
        total = int(match.group(1))
        failed = int(match.group(2))
        passed = total - failed

    # 檢查 errors
    match = re.search(r"(\d+)\s+errors?", stdout)
    if match:
        errored = int(match.group(1))
        passed = max(0, passed - errored)

    return passed, failed, errored


def _parse_minitest_items(stdout: str) -> list[TestItemResult]:
    """從 Minitest 輸出解析個別測試結果。"""
    items: list[TestItemResult] = []

    # Minitest format: "test_name = X.XX s = ."  or "test_name = X.XX s = F"
    pattern = re.compile(r"^(test_\w+)\s+=.*=\s+([.FE])", re.MULTILINE)
    for match in pattern.finditer(stdout):
        test_name = match.group(1)
        result = match.group(2)

        if result == ".":
            status = TestItemStatus.PASSED
        elif result == "F":
            status = TestItemStatus.FAILED
        else:
            status = TestItemStatus.ERROR

        items.append(
            TestItemResult(
                test_name=test_name,
                status=status,
                failure_reason=None,
            )
        )

    return items


def _parse_minitest_summary(stdout: str) -> tuple[int, int, int]:
    """從 Minitest 輸出解析 summary。"""
    passed = failed = errored = 0

    # Minitest format: "X runs, Y assertions, Z failures, W errors"
    match = re.search(
        r"(\d+)\s+runs?,\s+(\d+)\s+assertions?,\s+(\d+)\s+failures?,\s+(\d+)\s+errors?",
        stdout,
    )
    if match:
        runs = int(match.group(1))
        failed = int(match.group(3))
        errored = int(match.group(4))
        passed = runs - failed - errored

    return passed, failed, errored
