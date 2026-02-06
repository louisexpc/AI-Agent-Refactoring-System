"""Kotlin Language Plugin：處理 Kotlin 程式碼的測試生成與執行。

負責：
- 生成 golden capture 腳本（import + 呼叫 public API → JSON stdout）
- 用 kotlin/gradle 執行腳本
- 生成 JUnit5 test file（用 golden values 作為 expected）
- 用 gradle test + JaCoCo 執行 test
- kotlinc/gradle build 檢查 build
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
Generate a standalone Kotlin script that captures behavioral output.

Source files in this module:
{file_sections}

Dependent source files (signatures of imported modules):
{dependency_info}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Context (if converting from NodeJS/JavaScript):
- JS dynamic types → Kotlin static types (String, Int, List<T>, etc.)
- JS null/undefined → Kotlin nullable types (T?)
- JS callbacks/promises → Kotlin coroutines (suspend fun) or blocking calls
- JS object literals → Kotlin data classes
- MongoDB documents → PostgreSQL tables with proper schema

For database operations:
- Use JDBC with raw SQL queries (no ORM abstractions)
- Capture query results as structured data
- Test CRUD operations: INSERT, SELECT, UPDATE, DELETE
- Verify transaction behavior if applicable

Requirements:
- Use Kotlin `import` to import the source classes/functions
- The script must have a `main` function
- For class methods, instantiate the class first
- Use DESCRIPTIVE keys in the results map so we know what was tested.
  Format: "ClassName_methodName_scenario" or "functionName_scenario".
  Do NOT use generic keys like "result1", "test1", "output".
- Collect all results into a Map and print as JSON on the LAST line
- Use kotlinx.serialization or org.json or simple string building for JSON
- The LAST line must print JSON to stdout
- Do NOT include markdown code fences, return raw Kotlin code only
- Do NOT print anything else to stdout
"""

USER_TEST_GENERATION: str = """\
Generate a complete JUnit5 test file for behavioral validation.

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

Kotlin-specific considerations (if refactored from NodeJS):
- Verify null safety: nullable types should be handled properly
- Test data class equality (equals/hashCode)
- For suspend functions: use runBlocking in tests
- Verify type conversions are accurate (JS dynamic → Kotlin static)

Database testing (PostgreSQL with RAW SQL):
- Use JDBC directly: DriverManager.getConnection(...)
- Write explicit SQL queries (SELECT, INSERT, UPDATE, DELETE)
- Use @BeforeEach to set up test data, @AfterEach to clean up
- Test transaction commit/rollback behavior
- Verify foreign key constraints and data integrity
- Example pattern:
  ```
  val conn = DriverManager.getConnection(jdbcUrl, user, password)
  val stmt = conn.prepareStatement("SELECT * FROM users WHERE id = ?")
  stmt.setInt(1, userId)
  val rs = stmt.executeQuery()
  ```

Requirements:
1. For each golden output key, find the corresponding function/class in the new code
   and assert it produces the same value
2. Use Kotlin `import` to import the source classes
3. Use JUnit5 assertions (assertEquals, assertTrue, assertNotNull, etc.)
4. For mocking, use MockK or manual mocks
5. Mock any side effects (file I/O, network) as indicated in guidance
6. For database operations, use JDBC with raw SQL to verify state
7. If a golden key has no corresponding function in the new code, skip it with
   a comment explaining why
8. Do NOT include markdown code fences, return raw Kotlin code only
9. The test file must be runnable with `gradle test`
10. Use @Test annotation for each test method
11. Use @BeforeEach/@AfterEach for database setup/teardown
"""


# ---------------------------------------------------------------------------
# Plugin Implementation
# ---------------------------------------------------------------------------


class KotlinPlugin(LanguagePlugin):
    """Kotlin 語言插件。"""

    def generate_golden_script(
        self,
        source_code: str,
        module_paths: list[str],
        dep_signatures: str,
        guidance: dict[str, Any] | None,
        llm_client: Any,
    ) -> str:
        """生成 Kotlin golden capture 腳本。"""
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
        """用 kotlin 或 gradle 執行腳本。"""
        env = os.environ.copy()

        try:
            # 檢查是否有 build.gradle.kts
            gradle_build = work_dir / "build.gradle.kts"
            if not gradle_build.exists():
                gradle_build = work_dir / "build.gradle"

            if gradle_build.exists():
                # 使用 gradle run
                result = subprocess.run(
                    ["./gradlew", "run", "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(work_dir),
                    env=env,
                )
            else:
                # 直接用 kotlinc 編譯執行
                jar_path = script_path.with_suffix(".jar")
                compile_result = subprocess.run(
                    [
                        "kotlinc",
                        str(script_path),
                        "-include-runtime",
                        "-d",
                        str(jar_path),
                    ],
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

                result = subprocess.run(
                    ["java", "-jar", str(jar_path)],
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
        """生成 JUnit5 test file。"""
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
        """用 gradle test 執行測試。"""
        env = os.environ.copy()

        try:
            # 執行 gradle test with JaCoCo
            result = subprocess.run(
                ["./gradlew", "test", "jacocoTestReport", "--info"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )

            # 解析 JaCoCo coverage
            coverage_pct = _parse_jacoco_coverage(work_dir)

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
        """用 gradle build 或 kotlinc 檢查 Kotlin 專案。"""
        env = os.environ.copy()

        try:
            # 檢查是否有 gradle
            gradle_build = repo_dir / "build.gradle.kts"
            if not gradle_build.exists():
                gradle_build = repo_dir / "build.gradle"

            if gradle_build.exists():
                result = subprocess.run(
                    ["./gradlew", "compileKotlin", "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(repo_dir),
                    env=env,
                )
                return result.returncode == 0, result.stdout + result.stderr

            # 沒有 gradle，用 kotlinc 檢查
            kt_files = list(repo_dir.rglob("*.kt"))
            if not kt_files:
                return True, "No Kotlin files found"

            # 只檢查前幾個檔案避免太慢
            files_to_check = kt_files[:10]
            result = subprocess.run(
                ["kotlinc", "-Werror"]
                + [str(f) for f in files_to_check]
                + ["-d", "/tmp/kotlin_check"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(repo_dir),
                env=env,
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
        """解析 JUnit5/Gradle 測試輸出。"""
        test_items = _parse_gradle_test_items(stdout + stderr)
        passed, failed, errored = _parse_gradle_test_summary(stdout + stderr)

        # 如果沒解析到，從 exit code 推斷
        if passed == 0 and failed == 0 and errored == 0:
            if exit_code == 0:
                passed = len(test_items) if test_items else 1
            else:
                failed = 1

        return passed, failed, errored, test_items

    def check_test_syntax(
        self,
        test_content: str,
    ) -> tuple[bool, str]:
        """檢查 Kotlin 測試檔案的語法。"""
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())
            test_file = temp_dir / "TestSyntaxCheck.kt"
            test_file.write_text(test_content, encoding="utf-8")

            result = subprocess.run(
                ["kotlinc", "-Werror", str(test_file), "-d", str(temp_dir / "out")],
                capture_output=True,
                text=True,
                timeout=60,
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
        """檢查 Kotlin 原始碼是否可編譯。"""
        try:
            if not module_files:
                return False, "No module files provided"

            env = os.environ.copy()

            # 檢查是否有 gradle
            gradle_build = work_dir / "build.gradle.kts"
            if not gradle_build.exists():
                gradle_build = work_dir / "build.gradle"

            if gradle_build.exists():
                result = subprocess.run(
                    ["./gradlew", "compileKotlin", "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(work_dir),
                    env=env,
                )
                if result.returncode != 0:
                    return False, result.stderr or result.stdout
                return True, ""

            # 沒有 gradle，用 kotlinc
            kt_files = [f for f in module_files if f.suffix == ".kt"]
            if not kt_files:
                return True, "No Kotlin files to check"

            result = subprocess.run(
                ["kotlinc"] + [str(f) for f in kt_files] + ["-d", "/tmp/kotlin_check"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(work_dir),
                env=env,
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
                f"Package: {_extract_kotlin_package(source_code)}\n"
                f"```kotlin\n{source_code}\n```"
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
        """生成 build.gradle.kts 和 execution.sh"""
        artifacts = {}

        # 1. 用 LLM 生成 build.gradle.kts
        gradle_path = output_dir / "build.gradle.kts"
        gradle_content = self._generate_gradle_with_llm(
            script_path=script_path,
            test_file_path=test_file_path,
            repo_dir=repo_dir,
            llm_client=llm_client,
        )
        gradle_path.write_text(gradle_content, encoding="utf-8")
        artifacts["requirements"] = gradle_path

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

    def _generate_gradle_with_llm(
        self,
        script_path: Path | None,
        test_file_path: Path | None,
        repo_dir: Path,
        llm_client: Any,
    ) -> str:
        """用 LLM 分析 import 並生成 build.gradle.kts"""
        target_file = script_path or test_file_path
        if not target_file or not target_file.exists():
            return self._default_gradle()

        code_content = target_file.read_text(encoding="utf-8")

        # 檢查現有 build.gradle.kts
        existing_gradle = repo_dir / "build.gradle.kts"
        if not existing_gradle.exists():
            existing_gradle = repo_dir / "build.gradle"
        existing_content = ""
        if existing_gradle.exists():
            existing_content = existing_gradle.read_text(encoding="utf-8")

        prompt = f"""Analyze the following Kotlin code and generate a build.gradle.kts.

Code to analyze:
```kotlin
{code_content}
```

Existing build.gradle.kts in repo (if any):
```kotlin
{existing_content if existing_content else "None"}
```

Task:
1. Extract all `import` statements and identify required dependencies
2. If existing build.gradle.kts exists, use it as base and add any missing dependencies
3. If no existing build.gradle.kts, generate from scratch
4. Always include these dependencies:
   - JUnit5 for testing
   - JaCoCo for coverage
   - kotlinx-serialization or org.json for JSON
   - JDBC driver for PostgreSQL (org.postgresql:postgresql)
5. Configure JaCoCo to output XML report
6. Use Kotlin JVM plugin

Output ONLY the build.gradle.kts content, no explanations."""

        gradle = llm_client.generate(prompt).strip()

        # 清理 LLM 輸出
        if gradle.startswith("```"):
            lines = gradle.split("\n")
            gradle = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        return gradle.strip() or self._default_gradle()

    def _default_gradle(self) -> str:
        """預設 build.gradle.kts"""
        return """plugins {
    kotlin("jvm") version "1.9.0"
    kotlin("plugin.serialization") version "1.9.0"
    application
    jacoco
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
    implementation("org.postgresql:postgresql:42.6.0")

    testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
    testImplementation("io.mockk:mockk:1.13.8")
}

tasks.test {
    useJUnitPlatform()
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required.set(true)
        html.required.set(true)
    }
}

application {
    mainClass.set("MainKt")
}
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

        # 偵測 SQL fixture（用於 DB 初始化）
        db_init_script = ""
        sql_fixtures = list(repo_dir.glob("test_data/*.sql"))
        if not sql_fixtures:
            sql_fixtures = list(repo_dir.glob("*.sql"))
        if sql_fixtures:
            sql_file = sql_fixtures[0]
            sql_path = to_sandbox_path(sql_file)
            db_name = sql_file.stem
            db_init_script = f"""
# ========== DB Setup (auto-detected) ==========
if command -v psql &> /dev/null; then
    echo "Setting up PostgreSQL database..."
    psql -U postgres -c "DROP DATABASE IF EXISTS {db_name};" 2>/dev/null || true
    psql -U postgres -c "CREATE DATABASE {db_name};" 2>/dev/null || true
    psql -U postgres -d {db_name} -f {sql_path} 2>/dev/null || true
    echo "Database {db_name} initialized from {sql_file.name}"
elif command -v mysql &> /dev/null; then
    echo "Setting up MySQL database..."
    mysql -u root -e "DROP DATABASE IF EXISTS {db_name}; CREATE DATABASE {db_name};"
    mysql -u root {db_name} < {sql_path}
    echo "Database {db_name} initialized from {sql_file.name}"
fi
# ==============================================
"""

        if script_path:
            return f"""#!/bin/bash
set -e
{db_init_script}
# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"

# 1. Change to repo directory
cd "$REPO_DIR"

# 2. Make gradlew executable if exists
if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
fi

# 3. Build and run
if [ -f "./gradlew" ]; then
    ./gradlew run --quiet
elif [ -f "build.gradle.kts" ] || [ -f "build.gradle" ]; then
    gradle run --quiet
else
    # Compile with kotlinc and run
    kotlinc src/main/kotlin/*.kt -include-runtime -d app.jar
    java -jar app.jar
fi
"""
        elif test_file_path:
            return f"""#!/bin/bash
set -e
{db_init_script}

# Paths
REPO_DIR="{repo_dir_str}"
OUTPUT_DIR="{output_dir_str}"

# 1. Change to repo directory
cd "$REPO_DIR"

# 2. Make gradlew executable if exists
if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
fi

# 3. Run tests with coverage
if [ -f "./gradlew" ]; then
    ./gradlew test jacocoTestReport --info
elif [ -f "build.gradle.kts" ] || [ -f "build.gradle" ]; then
    gradle test jacocoTestReport --info
else
    echo "No Gradle build file found"
    exit 1
fi

# 4. Copy coverage report
if [ -f "build/reports/jacoco/test/jacocoTestReport.xml" ]; then
    cp build/reports/jacoco/test/jacocoTestReport.xml "$OUTPUT_DIR/"
fi
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
    if script.startswith("```kotlin"):
        script = script[len("```kotlin") :].strip()
    if script.startswith("```kt"):
        script = script[len("```kt") :].strip()
    if script.startswith("```"):
        first_nl = script.find("\n")
        if first_nl != -1:
            script = script[first_nl + 1 :]
        else:
            script = script[3:]
    if script.endswith("```"):
        script = script[:-3].strip()
    return script


def _extract_kotlin_package(source_code: str) -> str:
    """從 Kotlin 原始碼提取 package 名稱。"""
    match = re.search(r"^package\s+([\w.]+)", source_code, re.MULTILINE)
    if match:
        return match.group(1)
    return "(default package)"


def _parse_jacoco_coverage(work_dir: Path) -> float | None:
    """從 JaCoCo XML 報告解析覆蓋率。"""
    # JaCoCo XML 報告位置
    jacoco_xml = (
        work_dir / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.xml"
    )
    if not jacoco_xml.exists():
        # 嘗試其他可能位置
        jacoco_xml = work_dir / "jacocoTestReport.xml"

    if not jacoco_xml.exists():
        return None

    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(jacoco_xml)
        root = tree.getroot()

        # 找到 counter type="LINE"
        for counter in root.findall(".//counter[@type='LINE']"):
            missed = int(counter.get("missed", 0))
            covered = int(counter.get("covered", 0))
            total = missed + covered
            if total > 0:
                return round(covered / total * 100, 2)

        return None
    except Exception:
        return None


def _parse_gradle_test_items(output: str) -> list[TestItemResult]:
    """從 Gradle 測試輸出解析個別測試結果。"""
    items: list[TestItemResult] = []

    # Gradle 輸出格式: "TestClass > testMethod PASSED" 或 "FAILED"
    pattern = re.compile(r"(\S+)\s+>\s+(\S+)\s+(PASSED|FAILED|SKIPPED)", re.MULTILINE)

    for match in pattern.finditer(output):
        class_name = match.group(1)
        method_name = match.group(2)
        status_str = match.group(3)

        test_name = f"{class_name}.{method_name}"

        if status_str == "PASSED":
            status = TestItemStatus.PASSED
        elif status_str == "FAILED":
            status = TestItemStatus.FAILED
        else:
            status = TestItemStatus.SKIPPED

        items.append(
            TestItemResult(
                test_name=test_name,
                status=status,
                failure_reason=None,
            )
        )

    return items


def _parse_gradle_test_summary(output: str) -> tuple[int, int, int]:
    """從 Gradle 輸出解析測試 summary。"""
    passed = failed = errored = 0

    # Gradle format: "X tests completed, Y failed"
    match = re.search(r"(\d+)\s+tests?\s+completed", output)
    if match:
        total = int(match.group(1))
        passed = total

    match = re.search(r"(\d+)\s+failed", output)
    if match:
        failed = int(match.group(1))
        passed = max(0, passed - failed)

    match = re.search(r"(\d+)\s+skipped", output)
    if match:
        skipped = int(match.group(1))
        passed = max(0, passed - skipped)

    return passed, failed, errored
