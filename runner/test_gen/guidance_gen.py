"""Phase 2：LLM 生成測試指引文件。

針對每個來源檔案，讓 LLM 分析原始碼並產出測試時需注意的
副作用、mock 建議、非確定性行為等指引。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from shared.test_types import SourceFile, TestGuidance, TestGuidanceIndex


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
        llm_client: LLM 呼叫介面，None 表示使用 stub。
    """

    llm_client: Any = None
    repo_dir: Any = None

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
            if self.llm_client is None:
                guidances.append(TestGuidance(module_path=sf.path))
                continue

            prompt = GUIDANCE_PROMPT_TEMPLATE.format(
                module_path=sf.path,
                source_code=sf.read_content(self.repo_dir),
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
        if self.llm_client is None:
            return TestGuidance(module_path=source_file.path)

        prompt = GUIDANCE_PROMPT_TEMPLATE.format(
            module_path=source_file.path,
            source_code=source_file.read_content(self.repo_dir),
        )
        response = self.llm_client.generate(prompt)
        return self._parse_response(source_file.path, response)

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
