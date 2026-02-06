"""Rust Language Plugin：處理 Rust 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（執行舊 code → JSON stdout）
- 用 cargo run 執行腳本
- 生成 Rust test file（用 golden values 作為 expected）
- 用 cargo test 執行 test
- cargo build 檢查 build
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
Generate a standalone Rust program that captures behavioral output.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- Create a main() function that calls the functions from the source
- Use `mod` or `use` to import the source module
- Use serde_json to output results as JSON
- For each function call, use descriptive keys like "FunctionName_scenario"
- Do NOT use generic keys like "result1", "test1", "output"
- Output JSON to stdout using println! with serde_json::to_string
- Add `serde` and `serde_json` as dependencies if needed
- No markdown code fences, return raw Rust code only
- Runnable with: cargo run
"""

USER_TEST_GENERATION: str = """\
Generate a complete Rust test module for behavioral validation.

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
1. Create a test module with #[cfg(test)] mod tests
2. Use #[test] attribute for each test function
3. Use assert_eq!, assert!, or custom assertions
4. Test function names: test_<name> following Rust conventions
5. For floating point comparisons, use approximate equality
6. Use mockall or manual mocks for side effects if needed
7. If a golden key has no corresponding function, skip with comment
8. No markdown code fences, return raw Rust code only
9. Runnable with: cargo test
10. Import necessary items with `use super::*;` or specific imports
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class RustPlugin(LanguagePlugin):
    """Rust 語言插件。"""

    def _setup_rust_env(self) -> dict[str, str]:
        """設置 Rust 執行環境變數。"""
        env = os.environ.copy()
        # 加入常見的 Cargo/Rust 安裝路徑
        cargo_paths = [
            os.path.expanduser("~/.cargo/bin"),
            "/usr/local/cargo/bin",
        ]
        existing_path = env.get("PATH", "")
        for cargo_path in cargo_paths:
            if os.path.exists(cargo_path) and cargo_path not in existing_path:
                env["PATH"] = f"{cargo_path}:{existing_path}"
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
        """生成 Rust golden capture 腳本。"""
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
        """用 cargo run 執行 Rust 腳本。"""
        env = self._setup_rust_env()

        try:
            # 檢查是否有 Cargo.toml
            cargo_toml = work_dir / "Cargo.toml"
            if not cargo_toml.exists():
                # 建立臨時 Cargo 專案
                return self._run_standalone_rust(script_path, work_dir, timeout, env)

            # 使用現有 Cargo 專案
            result = subprocess.run(
                ["cargo", "run", "--release"],
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
                coverage_pct=None,  # Rust coverage 需要額外工具如 tarpaulin
            )

        except subprocess.TimeoutExpired:
            return TestRunResult(exit_code=-1, stderr="TIMEOUT")
        except Exception as exc:
            return TestRunResult(exit_code=-1, stderr=str(exc)[:500])

    def _run_standalone_rust(
        self,
        script_path: Path,
        work_dir: Path,
        timeout: int,
        env: dict[str, str],
    ) -> TestRunResult:
        """執行獨立的 Rust 檔案（沒有 Cargo.toml）。"""
        try:
            # 用 rustc 直接編譯
            output_binary = script_path.with_suffix("")
            compile_result = subprocess.run(
                ["rustc", "-o", str(output_binary), str(script_path)],
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
                    stderr=f"Compilation failed:\n{compile_result.stderr}",
                )

            # 執行
            run_result = subprocess.run(
                [str(output_binary)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            return TestRunResult(
                exit_code=run_result.returncode,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                coverage_pct=None,
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
        """生成 Rust test module。"""
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
        """用 cargo test 執行 Rust 測試。"""
        env = self._setup_rust_env()

        try:
            # 檢查是否有 Cargo.toml
            cargo_toml = work_dir / "Cargo.toml"
            if not cargo_toml.exists():
                # 嘗試在 source_dirs 中找 Cargo.toml
                if source_dirs:
                    for src_dir in source_dirs:
                        potential_cargo = work_dir / src_dir / "Cargo.toml"
                        if potential_cargo.exists():
                            work_dir = work_dir / src_dir
                            break

            # 複製測試檔案到適當位置（如果需要）
            if test_file_path.parent != work_dir / "src":
                target_dir = work_dir / "src"
                target_dir.mkdir(parents=True, exist_ok=True)

                # 如果是獨立測試檔案，可能需要整合到現有模組
                # 這裡簡單起見，假設測試已經在正確位置

            # 執行 cargo test
            result = subprocess.run(
                ["cargo", "test", "--", "--nocapture"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # 解析 coverage（需要 cargo-tarpaulin）
            coverage_pct = _parse_rust_coverage(work_dir, result.stdout)

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

    def check_build(
        self,
        repo_dir: Path,
        timeout: int,
    ) -> tuple[bool, str]:
        """用 cargo build 檢查 Rust 專案。"""
        env = self._setup_rust_env()

        # 找到所有包含 Cargo.toml 的目錄
        cargo_dirs = []
        for cargo_file in repo_dir.rglob("Cargo.toml"):
            cargo_dirs.append(cargo_file.parent)

        if not cargo_dirs:
            # 沒有 Cargo.toml，嘗試用 rustc 檢查單獨的 .rs 檔案
            rs_files = list(repo_dir.rglob("*.rs"))
            if not rs_files:
                return True, "No Rust files found"

            all_output = []
            all_success = True
            for rs_file in rs_files:
                try:
                    result = subprocess.run(
                        ["rustc", "--emit=metadata", "-o", "/dev/null", str(rs_file)],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=str(repo_dir),
                        env=env,
                    )
                    if result.returncode != 0:
                        all_success = False
                        all_output.append(f"{rs_file.name}: {result.stderr}")
                    else:
                        all_output.append(f"{rs_file.name}: OK")
                except Exception as exc:
                    return False, f"Error checking {rs_file.name}: {str(exc)[:200]}"

            return all_success, "\n".join(all_output)

        # 有 Cargo.toml，使用 cargo check
        all_success = True
        all_output = []

        for cargo_dir in cargo_dirs:
            try:
                result = subprocess.run(
                    ["cargo", "check"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cargo_dir),
                    env=env,
                )
                rel_path = cargo_dir.relative_to(repo_dir)
                all_output.append(f"Dir: {rel_path}\n{result.stdout}{result.stderr}")
                if result.returncode != 0:
                    all_success = False
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT in {cargo_dir}"
            except Exception as exc:
                return False, f"Error in {cargo_dir}: {str(exc)[:200]}"

        return all_success, "\n".join(all_output)

    def parse_test_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> tuple[int, int, int, list[TestItemResult]]:
        """解析 cargo test 輸出。"""
        test_items = _parse_rust_test_items(stdout)
        passed, failed, errored = _parse_rust_test_summary(stdout, exit_code)
        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 Rust 測試檔案的語法。"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())

            # 建立最小 Cargo 專案
            cargo_toml = temp_dir / "Cargo.toml"
            cargo_toml.write_text(
                '[package]\nname = "syntax_check"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )

            src_dir = temp_dir / "src"
            src_dir.mkdir()

            # 寫入測試內容（作為 lib.rs 的一部分）
            lib_rs = src_dir / "lib.rs"
            lib_rs.write_text(test_content, encoding="utf-8")

            env = self._setup_rust_env()

            # 使用 cargo check
            result = subprocess.run(
                ["cargo", "check"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(temp_dir),
                env=env,
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
        """檢查 Rust 原始碼是否可編譯。"""
        try:
            if not module_files:
                return False, "No module files provided"

            env = self._setup_rust_env()

            # 檢查是否有 Cargo.toml
            cargo_toml = work_dir / "Cargo.toml"
            if cargo_toml.exists():
                # 使用 cargo check
                result = subprocess.run(
                    ["cargo", "check"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(work_dir),
                    env=env,
                )

                if result.returncode != 0:
                    return False, result.stderr
                return True, ""

            # 沒有 Cargo.toml，逐一檢查 .rs 檔案
            errors = []
            for rs_file in module_files:
                if rs_file.suffix != ".rs":
                    continue

                result = subprocess.run(
                    ["rustc", "--emit=metadata", "-o", "/dev/null", str(rs_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(work_dir),
                    env=env,
                )

                if result.returncode != 0:
                    errors.append(f"{rs_file.name}: {result.stderr}")

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
                f"Module: {Path(module_paths[0]).stem}\n"
                f"```rust\n{source_code}\n```"
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
        """生成 Cargo.toml 和 execution.sh"""
        artifacts = {}

        # 1. 用 LLM 生成或補充 Cargo.toml
        cargo_path = output_dir / "Cargo.toml"
        cargo_content = self._generate_cargo_toml_with_llm(
            script_path=script_path,
            test_file_path=test_file_path,
            repo_dir=repo_dir,
            llm_client=llm_client,
        )
        cargo_path.write_text(cargo_content, encoding="utf-8")
        artifacts["requirements"] = cargo_path

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
                output_dir=output_dir,
                sandbox_base=sandbox_base,
                local_base=local_base,
            )
            sh_path.write_text(sh_content, encoding="utf-8")
            sh_path.chmod(0o755)
            artifacts["execution_sh"] = sh_path

        return artifacts

    def _generate_cargo_toml_with_llm(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        llm_client: Any,
    ) -> str:
        """用 LLM 分析 use statements 並生成 Cargo.toml"""
        target_file = script_path or test_file_path
        if not target_file or not target_file.exists():
            return self._default_cargo_toml()

        code_content = target_file.read_text(encoding="utf-8")

        # 檢查現有 Cargo.toml
        existing_cargo = repo_dir / "Cargo.toml"
        existing_content = ""
        if existing_cargo.exists():
            existing_content = existing_cargo.read_text(encoding="utf-8")

        prompt = f"""Analyze the following Rust code and generate a Cargo.toml.

Code to analyze:
```rust
{code_content}
```

Existing Cargo.toml in repo (if any):
```toml
{existing_content if existing_content else "None"}
```

Task:
1. Extract all `use` statements and identify required crates
2. Determine appropriate versions for dependencies
3. If existing Cargo.toml exists, merge and enhance it
4. Always include serde and serde_json for JSON output
5. Use edition = "2021"

Output ONLY the Cargo.toml content, no explanations."""

        cargo_toml = llm_client.generate(prompt).strip()

        # 清理 LLM 輸出
        if cargo_toml.startswith("```"):
            lines = cargo_toml.split("\n")
            cargo_toml = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        return cargo_toml.strip() or self._default_cargo_toml()

    def _default_cargo_toml(self) -> str:
        """預設 Cargo.toml"""
        return """[package]
name = "test_runner"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
"""

    def _generate_sh_with_template(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
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

        if script_path:
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"

# 1. Change to repo directory
cd "$REPO_DIR"

# 2. Build and run
cargo run --release
"""
        elif test_file_path:
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"

# 1. Change to repo directory
cd "$REPO_DIR"

# 2. Install cargo-tarpaulin if not present
if ! command -v cargo-tarpaulin &> /dev/null; then
    echo "Installing cargo-tarpaulin..."
    cargo install cargo-tarpaulin --locked || true
fi

# 3. Run tests with coverage
cargo tarpaulin --out Json --output-dir "$OUTPUT_DIR" -- --nocapture 2>/dev/null || \\
cargo test -- --nocapture
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
    if script.startswith("```rust"):
        script = script[len("```rust") :].strip()
    if script.startswith("```rs"):
        script = script[len("```rs") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _parse_rust_coverage(work_dir: Path, stdout: str) -> float | None:
    """解析 Rust coverage（需要 cargo-tarpaulin）。

    tarpaulin 輸出格式：
    XX.XX% coverage, X/Y lines covered
    """
    # 從 stdout 解析 tarpaulin 輸出
    match = re.search(r"([\d.]+)%\s+coverage", stdout)
    if match:
        return float(match.group(1))

    # 嘗試讀取 tarpaulin 報告檔
    tarpaulin_json = work_dir / "tarpaulin-report.json"
    if tarpaulin_json.exists():
        try:
            data = json.loads(tarpaulin_json.read_text(encoding="utf-8"))
            if "coverage" in data:
                return float(data["coverage"])
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def _parse_rust_test_items(stdout: str) -> list[TestItemResult]:
    """從 cargo test 輸出解析個別測試結果。

    cargo test 輸出格式：
    test tests::test_name ... ok
    test tests::test_name ... FAILED
    """
    items: list[TestItemResult] = []

    # 匹配 "test <name> ... ok/FAILED/ignored"
    pattern = re.compile(r"^test\s+(\S+)\s+\.\.\.\s+(ok|FAILED|ignored)", re.MULTILINE)

    for match in pattern.finditer(stdout):
        test_name = match.group(1)
        status_str = match.group(2)

        if status_str == "ok":
            status = TestItemStatus.PASSED
        elif status_str == "FAILED":
            status = TestItemStatus.FAILED
        elif status_str == "ignored":
            status = TestItemStatus.SKIPPED
        else:
            status = TestItemStatus.ERROR

        # 嘗試解析失敗原因
        failure_reason = None
        if status == TestItemStatus.FAILED:
            failure_reason = _extract_rust_failure_reason(stdout, test_name)

        items.append(
            TestItemResult(
                test_name=test_name,
                status=status,
                failure_reason=failure_reason,
            )
        )

    return items


def _extract_rust_failure_reason(stdout: str, test_name: str) -> str | None:
    """從 cargo test 輸出提取特定測試的失敗原因。"""
    # Rust 測試失敗會有類似這樣的輸出：
    # ---- tests::test_name stdout ----
    # thread 'tests::test_name' panicked at ...
    pattern = re.compile(
        rf"---- {re.escape(test_name)} stdout ----\n(.*?)(?=\n----|\nfailures:|\Z)",
        re.DOTALL,
    )
    match = pattern.search(stdout)
    if match:
        failure_text = match.group(1).strip()
        # 取前 500 字元
        if len(failure_text) > 500:
            failure_text = failure_text[:500] + "..."
        return failure_text
    return None


def _parse_rust_test_summary(stdout: str, exit_code: int) -> tuple[int, int, int]:
    """從 cargo test 輸出解析 passed/failed/errored 數量。

    格式：test result: ok. X passed; Y failed; Z ignored; ...
    """
    passed = failed = errored = 0

    # 匹配 "test result: ..."
    match = re.search(
        r"test result:.*?(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+ignored",
        stdout,
    )
    if match:
        passed = int(match.group(1))
        failed = int(match.group(2))
        # ignored 不算 errored

    # 如果 exit_code != 0 但沒解析到結果，視為錯誤
    if exit_code != 0 and passed == 0 and failed == 0:
        errored = 1

    return passed, failed, errored
