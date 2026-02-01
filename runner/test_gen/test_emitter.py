"""Phase 5：產出目標語言的可執行測試原始碼。

根據 TestInput 與 GoldenRecord，讓 LLM 生成
目標語言的測試檔案（pytest / go test / jest 等），
使評審可實際執行並量測 coverage。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.test_types import (
    EmittedTestFile,
    GoldenRecord,
    GoldenSnapshot,
    TestGuidanceIndex,
    TestInput,
)

EMIT_PROMPT_TEMPLATE: str = """\
You are a senior test engineer. Generate {language} test source code
based on the following information.

Target function: {function_name}
File path: {module_path}
Signature: {signature}

Test cases:
{test_cases_json}

Requirements:
1. Use the standard test framework for {language}
   (Python: pytest, Go: testing, TypeScript: jest)
2. Each test case should correspond to one test function
3. Use the golden output as the expected value in assertions
4. Do NOT include markdown code fences, return raw source code only
"""


@dataclass
class TestCodeEmitter:
    """將測試資料轉為可執行測試原始碼。

    當 ``llm_client`` 為 None 時，使用模板生成基礎測試程式碼。

    Args:
        target_language: 目標語言（python、go、typescript）。
        llm_client: LLM 呼叫介面，None 表示使用模板生成。
    """

    target_language: str = "python"
    llm_client: Any = None

    def emit(
        self,
        inputs: list[TestInput],
        golden: GoldenSnapshot,
        guidance_index: TestGuidanceIndex | None = None,
    ) -> list[EmittedTestFile]:
        """生成可執行測試檔案。

        Args:
            inputs: 測試輸入清單。
            golden: golden output 集合。
            guidance_index: 測試指引索引（可選）。

        Returns:
            產出的測試檔案清單。
        """
        golden_map: dict[str, GoldenRecord] = {r.input_id: r for r in golden.records}

        # 按 module_path 分組
        groups: dict[str, list[tuple[TestInput, GoldenRecord | None]]] = {}
        for inp in inputs:
            entry_parts = inp.entry_id.split("::")
            module_path = entry_parts[0] if len(entry_parts) > 1 else inp.entry_id
            record = golden_map.get(inp.input_id)
            groups.setdefault(module_path, []).append((inp, record))

        files: list[EmittedTestFile] = []
        for module_path, cases in groups.items():
            emitted = self._emit_for_module(module_path, cases)
            if emitted is not None:
                files.append(emitted)

        return files

    def _emit_for_module(
        self,
        module_path: str,
        cases: list[tuple[TestInput, GoldenRecord | None]],
    ) -> EmittedTestFile | None:
        """為單一模組生成測試檔。

        Args:
            module_path: 模組路徑。
            cases: 該模組的 (input, golden) 配對清單。

        Returns:
            EmittedTestFile 或 None（無法生成時）。
        """
        entry_ids = list({inp.entry_id for inp, _ in cases})

        if self.llm_client is not None:
            return self._emit_with_llm(module_path, cases, entry_ids)

        # Stub：使用模板生成
        return self._emit_with_template(module_path, cases, entry_ids)

    def _emit_with_template(
        self,
        module_path: str,
        cases: list[tuple[TestInput, GoldenRecord | None]],
        entry_ids: list[str],
    ) -> EmittedTestFile:
        """用模板生成 Python pytest 測試檔（stub 模式）。

        Args:
            module_path: 模組路徑。
            cases: 測試案例配對。
            entry_ids: 涵蓋的 entry_id 清單。

        Returns:
            EmittedTestFile。
        """
        test_path = self._derive_test_path(module_path)
        lines = [
            '"""Auto-generated golden master tests."""',
            "",
            "import json",
            "import pytest",
            "",
        ]

        for inp, golden_rec in cases:
            func_name = inp.entry_id.split("::")[-1] if "::" in inp.entry_id else "func"
            test_name = f"test_{func_name}_{inp.input_id[:8]}"
            expected = (
                json.dumps(golden_rec.output, default=str) if golden_rec else "None"
            )
            lines.append(f"def {test_name}():")
            lines.append(
                f'    """Test {func_name} with input: {inp.description or "auto"}."""'
            )
            lines.append(f"    # Input: {json.dumps(inp.args)}")
            lines.append(f"    expected = {expected}")
            lines.append(f"    # TODO: call {func_name} and assert result == expected")
            lines.append("    assert expected is not None")
            lines.append("")

        content = "\n".join(lines)
        return EmittedTestFile(
            path=test_path,
            language=self.target_language,
            content=content,
            entry_ids=entry_ids,
        )

    def _emit_with_llm(
        self,
        module_path: str,
        cases: list[tuple[TestInput, GoldenRecord | None]],
        entry_ids: list[str],
    ) -> EmittedTestFile:
        """用 LLM 生成測試原始碼。

        Args:
            module_path: 模組路徑。
            cases: 測試案例配對。
            entry_ids: 涵蓋的 entry_id 清單。

        Returns:
            EmittedTestFile。
        """
        test_cases = []
        for inp, golden_rec in cases:
            test_cases.append(
                {
                    "function": inp.entry_id.split("::")[-1]
                    if "::" in inp.entry_id
                    else inp.entry_id,
                    "args": inp.args,
                    "expected_output": golden_rec.output if golden_rec else None,
                    "description": inp.description,
                }
            )

        func_name = cases[0][0].entry_id.split("::")[-1] if cases else "unknown"
        prompt = EMIT_PROMPT_TEMPLATE.format(
            language=self.target_language,
            function_name=func_name,
            module_path=module_path,
            signature="(see test cases)",
            test_cases_json=json.dumps(test_cases, indent=2, default=str),
        )
        response = self.llm_client.generate(prompt)
        test_path = self._derive_test_path(module_path)

        return EmittedTestFile(
            path=test_path,
            language=self.target_language,
            content=response,
            entry_ids=entry_ids,
        )

    def _derive_test_path(self, module_path: str) -> str:
        """根據模組路徑推導測試檔路徑。

        Args:
            module_path: 原始模組路徑。

        Returns:
            測試檔案路徑。
        """
        p = Path(module_path)
        ext_map = {
            "python": ".py",
            "go": "_test.go",
            "typescript": ".test.ts",
            "javascript": ".test.js",
        }
        ext = ext_map.get(self.target_language, ".py")

        if self.target_language == "go":
            return str(p.with_suffix(ext))
        return str(p.parent / f"test_{p.stem}{ext}")
