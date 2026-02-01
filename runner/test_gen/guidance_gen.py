"""Phase 2：LLM 生成測試指引文件。

針對每個模組，讓 LLM 分析原始碼並產出測試時需注意的
副作用、mock 建議、非確定性行為等指引。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from shared.ingestion_types import DepGraphL0, RepoIndex
from shared.test_types import TestGuidance, TestGuidanceIndex


class LLMClient(Protocol):
    """LLM 呼叫介面。

    實作此 Protocol 即可替換不同的 LLM provider。
    """

    def generate(self, prompt: str) -> str:
        """送出 prompt 並取得回應文字。

        Args:
            prompt: 完整 prompt 文字。

        Returns:
            LLM 回應文字。
        """
        ...


GUIDANCE_PROMPT_TEMPLATE: str = """\
You are a senior test engineer. Analyze the following source code
and return testing guidance in JSON format.

File path: {module_path}

```
{source_code}
```

Return the following JSON format (do NOT include markdown code fences):
{{
  "module_path": "{module_path}",
  "side_effects": ["list side effects such as file I/O, network, DB, etc."],
  "mock_recommendations": ["list functions/deps that should be mocked"],
  "nondeterminism_notes": "describe nondeterministic behavior or null",
  "external_deps": ["list external dependencies"]
}}
"""


@dataclass
class TestGuidanceGenerator:
    """LLM 驅動的測試指引生成器。

    當 ``llm_client`` 為 None 時，回傳空指引（供無 LLM 環境測試）。

    Args:
        repo_dir: snapshot 中的 repo 目錄。
        llm_client: LLM 呼叫介面，None 表示使用 stub。
    """

    repo_dir: Path
    llm_client: Any = None

    def build(
        self,
        dep_graph: DepGraphL0,
        repo_index: RepoIndex,
    ) -> TestGuidanceIndex:
        """為每個模組生成測試指引。

        Args:
            dep_graph: L0 依賴圖。
            repo_index: 檔案索引。

        Returns:
            所有模組的測試指引索引。
        """
        guidances: list[TestGuidance] = []

        for node in dep_graph.nodes:
            file_path = self.repo_dir / node.path
            if not file_path.is_file():
                continue

            if self.llm_client is None:
                # Stub：回傳空指引
                guidances.append(TestGuidance(module_path=node.path))
                continue

            source = file_path.read_text(encoding="utf-8", errors="replace")
            prompt = GUIDANCE_PROMPT_TEMPLATE.format(
                module_path=node.path,
                source_code=source,
            )
            response = self.llm_client.generate(prompt)
            guidance = self._parse_response(node.path, response)
            guidances.append(guidance)

        return TestGuidanceIndex(guidances=guidances)

    def _parse_response(self, module_path: str, response: str) -> TestGuidance:
        """解析 LLM 回應為 TestGuidance。

        解析失敗時回傳空指引而非拋錯，確保 pipeline 不中斷。

        Args:
            module_path: 模組路徑。
            response: LLM 回應文字。

        Returns:
            解析後的 TestGuidance。
        """
        import json

        try:
            data = json.loads(response)
            return TestGuidance.model_validate(data)
        except (json.JSONDecodeError, Exception):
            return TestGuidance(module_path=module_path)
