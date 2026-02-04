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
    """

    repo_dir: Path
    logs_dir: Path
    timeout_sec: int = 30

    def run(
        self,
        before_files: list[SourceFile],
        plugin: LanguagePlugin,
        llm_client: Any,
        guidance: TestGuidance | None = None,
        dep_graph: DepGraph | None = None,
    ) -> list[GoldenRecord]:
        """執行 module 的舊程式碼並收集 golden output。

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

        # 收集依賴 signatures
        dep_signatures = self._collect_dep_signatures(before_files, dep_graph)

        # 用 plugin 生成 golden capture 腳本
        guidance_dict = guidance.model_dump() if guidance else None
        script = plugin.generate_golden_script(
            source_code=source_code,
            module_paths=module_paths,
            dep_signatures=dep_signatures,
            guidance=guidance_dict,
            llm_client=llm_client,
        )

        # 寫入腳本
        safe_name = _safe_name(module_paths)
        script_path = self.logs_dir / f"{safe_name}_script.py"
        script_path.write_text(script, encoding="utf-8")

        # 計算 source_dirs
        source_dirs = list({str(Path(sf.path).parent) for sf in before_files})

        # 執行並收集結果
        start = time.monotonic()
        run_result = plugin.run_with_coverage(
            script_path=script_path,
            work_dir=self.repo_dir,
            timeout=self.timeout_sec,
            source_dirs=source_dirs,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # 寫入 log
        log_path = self.logs_dir / f"{safe_name}.log"
        log_path.write_text(
            f"script:\n{script}\n\nstdout:\n{run_result.stdout}\n"
            f"stderr:\n{run_result.stderr}",
            encoding="utf-8",
        )

        # 建立 GoldenRecord
        file_path = (
            module_paths[0] if len(module_paths) == 1 else ",".join(module_paths)
        )
        record = GoldenRecord(
            file_path=file_path,
            output=_try_parse_json(run_result.stdout),
            exit_code=run_result.exit_code,
            stderr_snippet=run_result.stderr[:500] if run_result.stderr else None,
            duration_ms=duration_ms,
            coverage_pct=run_result.coverage_pct,
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
