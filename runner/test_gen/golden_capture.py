"""Module-level Golden Capture：執行舊程式碼，捕獲 golden output。

對一組 before_files（module mapping 的舊檔案），
聚合原始碼後由 LanguagePlugin 生成呼叫腳本並執行，記錄輸出作為標準答案。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.test_gen.dep_resolver import resolve_dependency_context
from runner.test_gen.plugins import LanguagePlugin
from shared.ingestion_types import DepGraph
from shared.test_types import GoldenRecord, SourceFile, TestGuidance

logger = logging.getLogger(__name__)


@dataclass
class ModuleGoldenCapture:
    """Module-level golden capture：聚合多個 before_files 並捕獲 golden output。

    Attributes:
        repo_dir: 舊程式碼的 repo 目錄。
        logs_dir: 執行日誌輸出目錄。
        timeout_sec: 單筆測試的超時秒數。
        max_retries: 生成 + 執行的最大重試次數。
    """

    repo_dir: Path
    logs_dir: Path
    timeout_sec: int = 30
    max_retries: int = 3

    def run(
        self,
        before_files: list[SourceFile],
        plugin: LanguagePlugin,
        llm_client: Any,
        guidance: TestGuidance | None = None,
        dep_graph: DepGraph | None = None,
    ) -> list[GoldenRecord]:
        """執行 module 的舊程式碼並收集 golden output。

        生成腳本 → 語法檢查 → 執行 → 驗證輸出，任一步驟失敗都會
        將錯誤回饋給 LLM 重新生成腳本（最多 max_retries 次）。

        Args:
            before_files: module mapping 中的舊檔案清單。
            plugin: 語言插件。
            llm_client: LLM 呼叫介面。
            guidance: 測試指引。
            dep_graph: 依賴圖。

        Returns:
            GoldenRecord 清單（通常只有一筆，代表整個 module 的 golden output）。
        """
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # 聚合所有 before_files 的原始碼
        source_code = self._aggregate_source(before_files)
        module_paths = [sf.path for sf in before_files]
        dep_signatures = self._collect_dep_signatures(before_files, dep_graph)
        guidance_dict = guidance.model_dump() if guidance else None

        safe_name = _safe_name(module_paths)
        script_path = self.logs_dir / f"{safe_name}_script.py"
        source_dirs = list({str(Path(sf.path).parent) for sf in before_files})
        file_path = (
            module_paths[0] if len(module_paths) == 1 else ",".join(module_paths)
        )

        # --- 統一 retry loop：生成 → 語法檢查 → 執行 → 驗證輸出 ---
        error_feedback: str | None = None
        run_result: Any = None
        script = ""
        duration_ms = 0

        for attempt in range(self.max_retries):
            if attempt > 0:
                logger.info(
                    "Retry golden capture, attempt %d/%d",
                    attempt + 1,
                    self.max_retries,
                )

            # 將上次錯誤回饋給 LLM
            if error_feedback is not None:
                if guidance_dict is not None:
                    guidance_dict["previous_error"] = error_feedback
                else:
                    guidance_dict = {"previous_error": error_feedback}

            # 1) 生成 script
            script = plugin.generate_golden_script(
                source_code=source_code,
                module_paths=module_paths,
                dep_signatures=dep_signatures,
                guidance=guidance_dict,
                llm_client=llm_client,
            )

            # 寫入腳本（每次覆寫，方便 debug）
            script_path.write_text(script, encoding="utf-8")

            # 2) 快速語法檢查
            compile_ok, error_msg = self._check_script_syntax(script, plugin)
            if not compile_ok:
                error_feedback = (
                    f"Script had syntax/compile errors:\n{error_msg}\n"
                    "Please fix these errors and regenerate."
                )
                logger.warning(
                    "Script syntax failed on attempt %d: %s",
                    attempt + 1,
                    error_msg[:300],
                )
                continue

            # 3) 執行腳本
            start = time.monotonic()
            run_result = plugin.run_with_coverage(
                script_path=script_path,
                work_dir=self.repo_dir,
                timeout=self.timeout_sec,
                source_dirs=source_dirs,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            # 4) 驗證執行結果
            output = _try_parse_json(run_result.stdout)
            if run_result.exit_code == 0 and isinstance(output, dict) and output:
                if attempt > 0:
                    logger.info("Golden capture succeeded on attempt %d", attempt + 1)
                break

            # 執行失敗：組裝錯誤回饋給 LLM
            error_parts: list[str] = []
            if run_result.exit_code != 0:
                error_parts.append(f"Script exited with code {run_result.exit_code}.")
            if run_result.stderr:
                error_parts.append(f"stderr:\n{run_result.stderr[-1000:]}")
            if not isinstance(output, dict) or not output:
                error_parts.append(
                    "Script did not produce valid JSON output on stdout. "
                    "Ensure the script prints ONLY a JSON object to stdout."
                )
            error_feedback = "\n".join(error_parts)
            logger.warning(
                "Golden capture execution failed on attempt %d: %s",
                attempt + 1,
                error_feedback[:300],
            )

        # --- 寫入最終 log ---
        log_path = self.logs_dir / f"{safe_name}.log"
        stdout_str = run_result.stdout if run_result else ""
        stderr_str = run_result.stderr if run_result else ""
        log_path.write_text(
            f"script:\n{script}\n\nstdout:\n{stdout_str}\n" f"stderr:\n{stderr_str}",
            encoding="utf-8",
        )

        # --- 建立 GoldenRecord ---
        record = GoldenRecord(
            file_path=file_path,
            output=_try_parse_json(stdout_str),
            exit_code=run_result.exit_code if run_result else -1,
            stderr_snippet=stderr_str[:500] if stderr_str else None,
            duration_ms=duration_ms,
            coverage_pct=run_result.coverage_pct if run_result else None,
        )

        if record.output is None:
            logger.warning(
                "Golden capture produced no output for %s after %d attempts. "
                "Downstream tests will lack golden anchoring.",
                file_path,
                self.max_retries,
            )

        return [record]

    def _aggregate_source(self, files: list[SourceFile]) -> str:
        """聚合多個檔案的原始碼，帶路徑標記。

        Args:
            files: 來源檔案清單。

        Returns:
            聚合後的原始碼字串。
        """
        if len(files) == 1:
            return files[0].read_content(self.repo_dir)

        sections: list[str] = []
        for sf in files:
            content = sf.read_content(self.repo_dir)
            sections.append(
                f"File: {sf.path}\n"
                f"Directory: {str(Path(sf.path).parent)}\n"
                f"Module name: {Path(sf.path).stem}\n"
                f"```\n{content}\n```"
            )
        return "\n\n".join(sections)

    def _collect_dep_signatures(
        self,
        files: list[SourceFile],
        dep_graph: DepGraph | None,
    ) -> str:
        """收集所有 before_files 的依賴 signatures。

        Args:
            files: 來源檔案清單。
            dep_graph: 依賴圖。

        Returns:
            依賴 signatures 字串。
        """
        if dep_graph is None:
            return ""

        seen: set[str] = set()
        parts: list[str] = []
        for sf in files:
            ctx = resolve_dependency_context(dep_graph, sf.path, self.repo_dir)
            if ctx and ctx not in seen:
                seen.add(ctx)
                parts.append(ctx)
        return "\n".join(parts)

    def _check_script_syntax(
        self,
        script: str,
        plugin: LanguagePlugin,
    ) -> tuple[bool, str]:
        """檢查 script 的語法（不執行）。

        Args:
            script: 生成的 script。
            plugin: 語言插件。

        Returns:
            (是否成功, 錯誤訊息) 元組。
        """
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py"
                if "python" in plugin.__class__.__name__.lower()
                else ".go",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(script)
                temp_path = Path(f.name)

            # 使用 Python 的 compile 或 Go 的 build 檢查
            if "python" in plugin.__class__.__name__.lower():
                try:
                    compile(script, temp_path.name, "exec")
                    return True, ""
                except SyntaxError as e:
                    return False, str(e)
            else:
                # 其他語言使用 plugin 的 check_build（但這需要完整的環境）
                # 暫時先跳過檢查
                return True, ""
        except Exception as e:
            return False, str(e)
        finally:
            if temp_path.exists():
                temp_path.unlink()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_name(module_paths: list[str]) -> str:
    """從 module paths 產生安全的檔名。"""
    if len(module_paths) == 1:
        return module_paths[0].replace("/", "_").replace(".", "_")
    # 多檔時用第一個檔名加 _module 後綴
    return module_paths[0].replace("/", "_").replace(".", "_") + "_module"


def _try_parse_json(text: str) -> str | dict | list | None:
    """嘗試將 stdout 解析為 JSON。

    Args:
        text: stdout 文字。

    Returns:
        解析後的物件或原始字串。
    """
    text = text.strip()
    if not text:
        return None
    last_line = text.split("\n")[-1].strip()
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
