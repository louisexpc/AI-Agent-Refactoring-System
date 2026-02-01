"""Phase 3：LLM 生成測試輸入資料。

根據 TestableEntry 的函式簽名與 TestGuidance 的指引，
讓 LLM 產出具體的測試輸入資料。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from shared.test_types import (
    TestableEntry,
    TestGuidance,
    TestGuidanceIndex,
    TestInput,
    TestInputSet,
)

INPUT_GEN_PROMPT_TEMPLATE: str = """\
You are a senior test engineer. Generate test input data for the following function.

Function: {function_name}
File: {module_path}
Signature: {signature}
Docstring: {docstring}

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism: {nondeterminism_notes}

Return a JSON array where each element is a test case:
[
  {{
    "args": {{"param1": "value1"}},
    "description": "description of the test case"
  }}
]

Generate at least 3 test cases covering: normal path,
boundary values, and error handling.
Do NOT include markdown code fences, return raw JSON only.
"""


@dataclass
class TestInputGenerator:
    """LLM 驅動的測試輸入生成器。

    當 ``llm_client`` 為 None 時，為每個 entry 產生一筆空輸入（stub）。

    Args:
        repo_dir: snapshot 中的 repo 目錄。
        llm_client: LLM 呼叫介面，None 表示使用 stub。
    """

    repo_dir: Path
    llm_client: Any = None

    def build(
        self,
        entries: list[TestableEntry],
        guidance_index: TestGuidanceIndex,
    ) -> TestInputSet:
        """為所有 entry 生成測試輸入。

        Args:
            entries: 可測試 entry point 清單。
            guidance_index: 測試指引索引。

        Returns:
            測試輸入集合。
        """
        guidance_map: dict[str, TestGuidance] = {
            g.module_path: g for g in guidance_index.guidances
        }
        inputs: list[TestInput] = []

        for entry in entries:
            guidance = guidance_map.get(entry.module_path)
            generated = self._generate_for_entry(entry, guidance)
            inputs.extend(generated)

        return TestInputSet(inputs=inputs)

    def _generate_for_entry(
        self,
        entry: TestableEntry,
        guidance: TestGuidance | None,
    ) -> list[TestInput]:
        """為單一 entry 生成測試輸入。

        Args:
            entry: 測試目標。
            guidance: 對應模組的測試指引。

        Returns:
            測試輸入清單。
        """
        if self.llm_client is None:
            return [
                TestInput(
                    input_id=uuid4().hex[:12],
                    entry_id=entry.entry_id,
                    args={},
                    description=f"stub input for {entry.function_name}",
                ),
            ]

        prompt = INPUT_GEN_PROMPT_TEMPLATE.format(
            function_name=entry.function_name,
            module_path=entry.module_path,
            signature=entry.signature or "(unknown)",
            docstring=entry.docstring or "(none)",
            side_effects=", ".join(guidance.side_effects) if guidance else "none",
            mock_recommendations=(
                ", ".join(guidance.mock_recommendations) if guidance else "none"
            ),
            nondeterminism_notes=(
                guidance.nondeterminism_notes if guidance else "none"
            ),
        )
        response = self.llm_client.generate(prompt)
        return self._parse_response(entry, response)

    def _parse_response(
        self,
        entry: TestableEntry,
        response: str,
    ) -> list[TestInput]:
        """解析 LLM 回應為 TestInput 清單。

        Args:
            entry: 測試目標。
            response: LLM 回應文字。

        Returns:
            解析後的測試輸入清單。
        """
        try:
            items = json.loads(response)
            if not isinstance(items, list):
                items = [items]
            return [
                TestInput(
                    input_id=uuid4().hex[:12],
                    entry_id=entry.entry_id,
                    args=item.get("args", {}),
                    description=item.get("description"),
                )
                for item in items
            ]
        except (json.JSONDecodeError, Exception):
            return [
                TestInput(
                    input_id=uuid4().hex[:12],
                    entry_id=entry.entry_id,
                    args={},
                    description=f"fallback input for {entry.function_name}",
                ),
            ]
