"""Phase 2：LLM 生成測試指引文件。

針對每個來源檔案，讓 LLM 分析原始碼並產出測試時需注意的
副作用、mock 建議、非確定性行為等指引。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.test_gen.dep_resolver import resolve_dependency_context
from shared.ingestion_types import DepGraph
from shared.test_types import SourceFile, TestGuidance, TestGuidanceIndex

logger = logging.getLogger(__name__)

GUIDANCE_PROMPT_TEMPLATE: str = """\
You are a senior test engineer. Analyze the following source code
and return testing guidance in JSON format.

File path: {module_path}

```
{source_code}
```

Dependent source files (signatures):
{dependency_info}

Return the following JSON format (do NOT include markdown code fences):
{{
  "module_path": "{module_path}",
  "side_effects": ["list side effects such as file I/O, network, DB, etc."],
  "mock_recommendations": ["list functions/deps that should be mocked"],
  "nondeterminism_notes": "describe nondeterministic behavior or null",
  "external_deps": ["list external dependencies"]
}}
"""


def _strip_markdown_fences(text: str) -> str:
    """移除 LLM 回應中的 markdown code fence。

    Args:
        text: LLM 回應文字。

    Returns:
        清理後的文字。
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


@dataclass
class TestGuidanceGenerator:
    """LLM 驅動的測試指引生成器。

    Args:
        llm_client: LLM 呼叫介面。
        repo_dir: repo 根目錄。
    """

    llm_client: Any
    repo_dir: Path
    dep_graph: DepGraph | None = None

    def build_for_files(
        self,
        source_files: list[SourceFile],
    ) -> TestGuidanceIndex:
        """為每個來源檔案生成測試指引。

        Args:
            source_files: 來源檔案清單。

        Returns:
            所有模組的測試指引索引。
        """
        guidances: list[TestGuidance] = []

        for sf in source_files:
            dep_info = resolve_dependency_context(
                self.dep_graph, sf.path, self.repo_dir
            )
            prompt = GUIDANCE_PROMPT_TEMPLATE.format(
                module_path=sf.path,
                source_code=sf.read_content(self.repo_dir),
                dependency_info=dep_info,
            )
            response = self.llm_client.generate(prompt)
            guidance = self._parse_response(sf.path, response)
            guidances.append(guidance)

        return TestGuidanceIndex(guidances=guidances)

    def build_for_single(self, source_file: SourceFile) -> TestGuidance:
        """為單一來源檔案生成測試指引。

        Args:
            source_file: 來源檔案。

        Returns:
            測試指引。
        """
        dep_info = resolve_dependency_context(
            self.dep_graph, source_file.path, self.repo_dir
        )
        prompt = GUIDANCE_PROMPT_TEMPLATE.format(
            module_path=source_file.path,
            source_code=source_file.read_content(self.repo_dir),
            dependency_info=dep_info,
        )
        response = self.llm_client.generate(prompt)
        return self._parse_response(source_file.path, response)

    def build_for_module(self, source_files: list[SourceFile]) -> TestGuidance:
        """為一組 module 檔案生成聚合的測試指引。

        聚合多個檔案的原始碼，產出單一 TestGuidance。

        Args:
            source_files: module 的來源檔案清單。

        Returns:
            聚合的測試指引。
        """
        if len(source_files) == 1:
            return self.build_for_single(source_files[0])

        # 聚合多檔原始碼
        sections: list[str] = []
        all_dep_info: list[str] = []
        for sf in source_files:
            sections.append(f"--- {sf.path} ---\n{sf.read_content(self.repo_dir)}")
            dep_info = resolve_dependency_context(
                self.dep_graph, sf.path, self.repo_dir
            )
            if dep_info:
                all_dep_info.append(dep_info)

        combined_code = "\n\n".join(sections)
        combined_deps = "\n".join(all_dep_info) if all_dep_info else "None"
        module_path = ",".join(sf.path for sf in source_files)

        prompt = GUIDANCE_PROMPT_TEMPLATE.format(
            module_path=module_path,
            source_code=combined_code,
            dependency_info=combined_deps,
        )
        response = self.llm_client.generate(prompt)
        return self._parse_response(module_path, response)

    def _parse_response(self, module_path: str, response: str) -> TestGuidance:
        """解析 LLM 回應為 TestGuidance。

        先清除 markdown code fence，再嘗試 JSON 解析。
        解析失敗時回傳空指引而非拋錯，確保 pipeline 不中斷。

        Args:
            module_path: 模組路徑。
            response: LLM 回應文字。

        Returns:
            解析後的 TestGuidance。
        """
        cleaned = _strip_markdown_fences(response)
        try:
            data = json.loads(cleaned)
            return TestGuidance.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to parse guidance for %s: %s", module_path, exc)
            return TestGuidance(module_path=module_path)
