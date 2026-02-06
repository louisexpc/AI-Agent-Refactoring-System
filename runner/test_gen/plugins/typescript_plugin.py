"""TypeScript Language Plugin：處理 TypeScript 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（import + 呼叫 public API → JSON stdout）
- 用 ts-node/tsx 執行腳本
- 生成 Jest/Vitest test file（用 golden values 作為 expected）
- 用 jest/vitest + coverage 執行 test
- tsc --noEmit 檢查 build
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
Generate a standalone TypeScript script that captures behavioral output.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- Use ES6 `import` to import the source module
- Script must be runnable with `npx ts-node script.ts` or `npx tsx script.ts`
- For class methods, instantiate the class first
- Use DESCRIPTIVE keys in the results object so we know what was tested.
  Format: "ClassName_methodName_scenario" or "functionName_scenario".
  Do NOT use generic keys like "result1", "test1", "output".
- Collect all results into an object and print as JSON on the LAST line
- The LAST line must be: console.log(JSON.stringify(results))
- Do NOT include markdown code fences, return raw TypeScript code only
- Do NOT print anything else to stdout
"""

USER_TEST_GENERATION: str = """\
Generate a complete Jest test file for behavioral validation.

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
2. Use ES6 `import` to import the source module
3. Use Jest expectations (expect(actual).toEqual(expected))
4. For mocking, use jest.mock() or jest.spyOn()
5. Mock any side effects (file I/O, network, DB) as indicated in guidance
6. If a golden key has no corresponding function in the new code, skip it with
   a comment explaining why
7. Do NOT include markdown code fences, return raw TypeScript code only
8. The test file must be self-contained and runnable with `npx jest test_file.ts`
9. Use describe() and test() or it() blocks
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class TypeScriptPlugin(LanguagePlugin):
    """TypeScript 語言插件。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 TypeScript golden capture 腳本。"""
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
        """用 ts-node 或 tsx 執行腳本。"""
        env = os.environ.copy()
        env["NODE_PATH"] = _build_node_path(work_dir, source_dirs)

        try:
            # 嘗試 tsx（更快），失敗則用 ts-node
            result = subprocess.run(
                ["npx", "tsx", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            if result.returncode != 0 and "tsx" in result.stderr.lower():
                # tsx 不存在，嘗試 ts-node
                result = subprocess.run(
                    ["npx", "ts-node", str(script_path)],
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
        """生成 Jest test file。"""
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
        """用 Jest 執行 test file。"""
        env = os.environ.copy()
        env["NODE_PATH"] = _build_node_path(work_dir, source_dirs)

        try:
            result = subprocess.run(
                [
                    "npx",
                    "jest",
                    str(test_file_path),
                    "--coverage",
                    "--coverageReporters=json-summary",
                    "--json",
                    f"--outputFile={work_dir / 'jest-results.json'}",
                    "--passWithNoTests",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # 解析 coverage
            coverage_pct = _parse_jest_coverage(work_dir)

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
        """用 tsc --noEmit 檢查 TypeScript 專案。"""
        try:
            # 檢查是否有 tsconfig.json
            tsconfig = repo_dir / "tsconfig.json"
            if tsconfig.exists():
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(repo_dir),
                )
            else:
                # 沒有 tsconfig，逐一檢查 .ts 檔案
                ts_files = list(repo_dir.rglob("*.ts"))
                ts_files = [f for f in ts_files if not f.name.endswith(".d.ts")]
                if not ts_files:
                    return True, "No TypeScript files found"

                result = subprocess.run(
                    ["npx", "tsc", "--noEmit", "--allowJs", "--checkJs", "false"]
                    + [str(f) for f in ts_files[:10]],  # 限制數量避免太慢
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(repo_dir),
                )

            return result.returncode == 0, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        except Exception as exc:
            return False, str(exc)[:500]

    def parse_test_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> tuple[int, int, int, list[TestItemResult]]:
        """解析 Jest 測試輸出。"""
        test_items = _parse_jest_items(stdout)
        passed, failed, errored = _parse_jest_summary(stdout)

        # 如果沒解析到，嘗試從 stderr
        if passed == 0 and failed == 0:
            passed, failed, errored = _parse_jest_summary(stderr)

        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 TypeScript 測試檔案的語法。"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())
            test_file = temp_dir / "test_syntax_check.ts"
            test_file.write_text(test_content, encoding="utf-8")

            # 建立最小 tsconfig
            tsconfig = temp_dir / "tsconfig.json"
            tsconfig.write_text(
                json.dumps(
                    {
                        "compilerOptions": {
                            "noEmit": True,
                            "esModuleInterop": True,
                            "skipLibCheck": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(temp_dir),
            )

            if result.returncode != 0:
                return False, result.stderr or result.stdout
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
        """檢查 TypeScript 原始碼是否可編譯。"""
        try:
            if not module_files:
                return False, "No module files provided"

            # 檢查是否有 tsconfig.json
            tsconfig = work_dir / "tsconfig.json"
            if tsconfig.exists():
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(work_dir),
                )
            else:
                ts_files = [f for f in module_files if f.suffix == ".ts"]
                if not ts_files:
                    return True, "No TypeScript files to check"

                result = subprocess.run(
                    ["npx", "tsc", "--noEmit", "--esModuleInterop"]
                    + [str(f) for f in ts_files],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(work_dir),
                )

            if result.returncode != 0:
                return False, result.stderr or result.stdout
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
                f"Module name: {Path(module_paths[0]).stem}\n"
                f"```typescript\n{source_code}\n```"
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
        """生成 package.json 和 execution.sh"""
        artifacts = {}

        # 1. 用 LLM 生成 package.json
        package_json_path = output_dir / "package.json"
        package_json_content = self._generate_package_json_with_llm(
            script_path=script_path,
            test_file_path=test_file_path,
            repo_dir=repo_dir,
            llm_client=llm_client,
        )
        package_json_path.write_text(package_json_content, encoding="utf-8")
        artifacts["requirements"] = package_json_path

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

    def _generate_package_json_with_llm(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        llm_client: Any,
    ) -> str:
        """用 LLM 分析 import 並生成 package.json"""
        target_file = script_path or test_file_path
        if not target_file or not target_file.exists():
            return self._default_package_json()

        code_content = target_file.read_text(encoding="utf-8")

        # 檢查現有 package.json
        existing_package = repo_dir / "package.json"
        existing_content = ""
        if existing_package.exists():
            existing_content = existing_package.read_text(encoding="utf-8")

        prompt = f"""Analyze the following TypeScript code and generate a package.json.

Code to analyze:
```typescript
{code_content}
```

Existing package.json in repo (if any):
```json
{existing_content if existing_content else "None"}
```

Task:
1. Extract all `import` statements and identify required npm packages
2. If existing package.json exists, use it as base and add any missing packages
3. If no existing package.json, generate from scratch
4. Always include these devDependencies:
   - typescript
   - ts-node or tsx
   - jest
   - @types/jest
   - ts-jest
5. Add a "test" script: "jest --coverage"
6. Use "type": "module" if ES modules are used

Output ONLY the package.json content (valid JSON), no explanations."""

        package_json = llm_client.generate(prompt).strip()

        # 清理 LLM 輸出
        if package_json.startswith("```"):
            lines = package_json.split("\n")
            package_json = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        # 驗證是否為有效 JSON
        try:
            json.loads(package_json)
            return package_json
        except json.JSONDecodeError:
            return self._default_package_json()

    def _default_package_json(self) -> str:
        """預設 package.json"""
        return json.dumps(
            {
                "name": "test-runner",
                "version": "1.0.0",
                "scripts": {
                    "test": "jest --coverage",
                    "build": "tsc --noEmit",
                },
                "devDependencies": {
                    "typescript": "^5.0.0",
                    "tsx": "^4.0.0",
                    "ts-node": "^10.0.0",
                    "jest": "^29.0.0",
                    "@types/jest": "^29.0.0",
                    "ts-jest": "^29.0.0",
                    "@types/node": "^20.0.0",
                },
            },
            indent=2,
        )

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

        # 建立 NODE_PATH
        node_path_parts = []
        if source_dirs:
            for src_dir in source_dirs:
                node_path_parts.append(f'"$REPO_DIR/{src_dir}"')
        node_path_parts.append('"$REPO_DIR/node_modules"')
        node_path_parts.append('"$REPO_DIR"')
        node_path_str = ":".join(node_path_parts)

        if script_path:
            script_str = to_sandbox_path(script_path)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
SCRIPT="{script_str}"

# 1. Install dependencies
cd "$REPO_DIR"
npm install 2>/dev/null || true
cd "$OUTPUT_DIR"
npm install

# 2. Set up NODE_PATH
export NODE_PATH="{node_path_str}${{NODE_PATH:+:$NODE_PATH}}"

# 3. Execute golden script
cd "$REPO_DIR"
npx tsx "$SCRIPT" 2>/dev/null || npx ts-node "$SCRIPT"
"""
        elif test_file_path:
            test_str = to_sandbox_path(test_file_path)
            return f"""#!/bin/bash
set -e

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"
TEST_FILE="{test_str}"

# 1. Install dependencies
cd "$REPO_DIR"
npm install 2>/dev/null || true
cd "$OUTPUT_DIR"
npm install

# 2. Set up NODE_PATH
export NODE_PATH="{node_path_str}${{NODE_PATH:+:$NODE_PATH}}"

# 3. Create jest config if not exists
if [ ! -f "$REPO_DIR/jest.config.js" ] && [ ! -f "$REPO_DIR/jest.config.ts" ]; then
    cat > "$OUTPUT_DIR/jest.config.js" << 'JESTCONFIG'
module.exports = {{
  preset: 'ts-jest',
  testEnvironment: 'node',
  coverageReporters: ['json-summary', 'text'],
}};
JESTCONFIG
fi

# 4. Execute tests with coverage
cd "$REPO_DIR"
npx jest "$TEST_FILE" --coverage --coverageDirectory="$OUTPUT_DIR/coverage" \\
    --config="${{OUTPUT_DIR}}/jest.config.js" 2>/dev/null || \\
npx jest "$TEST_FILE" --coverage --coverageDirectory="$OUTPUT_DIR/coverage"
"""
        else:
            return "#!/bin/bash\necho 'No script specified'\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_node_path(
    work_dir: Path,
    source_dirs: list[str] | None = None,
) -> str:
    """建構 NODE_PATH 環境變數。"""
    parts: list[str] = []

    if source_dirs:
        seen: set[str] = set()
        for d in source_dirs:
            abs_dir = str(work_dir / d)
            if abs_dir not in seen:
                seen.add(abs_dir)
                parts.append(abs_dir)

    # node_modules
    node_modules = work_dir / "node_modules"
    if node_modules.exists():
        parts.append(str(node_modules))

    parts.append(str(work_dir))

    existing = os.environ.get("NODE_PATH", "")
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
    if script.startswith("```typescript"):
        script = script[len("```typescript") :].strip()
    if script.startswith("```ts"):
        script = script[len("```ts") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _parse_jest_coverage(work_dir: Path) -> float | None:
    """從 Jest coverage 輸出解析覆蓋率。"""
    # Jest coverage-summary.json
    coverage_file = work_dir / "coverage" / "coverage-summary.json"
    if not coverage_file.exists():
        # 嘗試其他位置
        coverage_file = work_dir / "coverage-summary.json"

    if coverage_file.exists():
        try:
            data = json.loads(coverage_file.read_text(encoding="utf-8"))
            total = data.get("total", {})
            lines = total.get("lines", {})
            pct = lines.get("pct")
            if pct is not None:
                return float(pct)
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def _parse_jest_items(stdout: str) -> list[TestItemResult]:
    """從 Jest 輸出解析個別測試結果。"""
    items: list[TestItemResult] = []

    # Jest verbose format: "✓ test name (Xms)" or "✕ test name"
    pass_pattern = re.compile(r"[✓✔]\s+(.+?)(?:\s+\(\d+\s*m?s\))?$", re.MULTILINE)
    fail_pattern = re.compile(r"[✕✗]\s+(.+?)(?:\s+\(\d+\s*m?s\))?$", re.MULTILINE)

    for match in pass_pattern.finditer(stdout):
        items.append(
            TestItemResult(
                test_name=match.group(1).strip(),
                status=TestItemStatus.PASSED,
                failure_reason=None,
            )
        )

    for match in fail_pattern.finditer(stdout):
        items.append(
            TestItemResult(
                test_name=match.group(1).strip(),
                status=TestItemStatus.FAILED,
                failure_reason=None,
            )
        )

    return items


def _parse_jest_summary(stdout: str) -> tuple[int, int, int]:
    """從 Jest 輸出解析 summary。"""
    passed = failed = errored = 0

    # Jest format: "Tests: X passed, Y failed, Z total"
    match = re.search(r"Tests:\s+(\d+)\s+passed", stdout)
    if match:
        passed = int(match.group(1))

    match = re.search(r"(\d+)\s+failed", stdout)
    if match:
        failed = int(match.group(1))

    # 檢查 error
    match = re.search(r"(\d+)\s+error", stdout, re.IGNORECASE)
    if match:
        errored = int(match.group(1))

    return passed, failed, errored
