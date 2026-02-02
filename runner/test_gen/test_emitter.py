"""Phase 4：產出目標語言的可執行測試原始碼（file 級別）。

LLM 讀整個來源檔案 + guidance + golden output，
直接生成完整的測試檔（pytest / go test / jest）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.test_types import (
    EmittedTestFile,
    GoldenRecord,
    SourceFile,
    TestGuidance,
)

EMIT_PROMPT_TEMPLATE: str = """\
You are a senior test engineer. Generate a complete {language} test file
for the following source code.

File path: {module_path}

Source code:
```
{source_code}
```

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Golden output (expected behavior of the original code):
{golden_output}

Requirements:
1. Use the standard test framework for {language}
   (Python: pytest, Go: testing, TypeScript: jest)
2. Decide which functions/classes are worth testing
3. Generate test inputs: normal path, boundary values, error handling
4. Use the golden output as reference for expected values where applicable
5. Mock any side effects (file I/O, network, DB) as indicated in guidance
6. Do NOT include markdown code fences, return raw source code only
7. The test file must be self-contained and runnable
"""


@dataclass
class TestCodeEmitter:
    """將來源檔案轉為可執行測試原始碼（file 級別）。

    LLM 讀整個檔案後自行決定測哪些函式、用什麼 input。

    Args:
        target_language: 目標語言（python、go、typescript）。
        llm_client: LLM 呼叫介面。
        repo_dir: repo 根目錄。
    """

    target_language: str = "python"
    llm_client: Any = None
    repo_dir: Any = None

    def emit_for_file(
        self,
        source_file: SourceFile,
        guidance: TestGuidance | None = None,
        golden_record: GoldenRecord | None = None,
    ) -> EmittedTestFile:
        """為單一來源檔案生成測試檔。

        Args:
            source_file: 來源檔案。
            guidance: 測試指引。
            golden_record: golden output。

        Returns:
            產出的測試檔案。
        """
        return self._emit_with_llm(source_file, guidance, golden_record)

    def emit_for_files(
        self,
        source_files: list[SourceFile],
        guidances: dict[str, TestGuidance] | None = None,
        golden_map: dict[str, GoldenRecord] | None = None,
    ) -> list[EmittedTestFile]:
        """為多個來源檔案生成測試檔。

        Args:
            source_files: 來源檔案清單。
            guidances: path → TestGuidance 對照。
            golden_map: path → GoldenRecord 對照。

        Returns:
            產出的測試檔案清單。
        """
        results: list[EmittedTestFile] = []
        for sf in source_files:
            g = guidances.get(sf.path) if guidances else None
            gr = golden_map.get(sf.path) if golden_map else None
            results.append(self.emit_for_file(sf, g, gr))
        return results

    def _emit_with_llm(
        self,
        source_file: SourceFile,
        guidance: TestGuidance | None,
        golden_record: GoldenRecord | None,
    ) -> EmittedTestFile:
        """用 LLM 生成完整測試檔。

        Args:
            source_file: 來源檔案。
            guidance: 測試指引。
            golden_record: golden output。

        Returns:
            EmittedTestFile。
        """
        golden_str = "Not available"
        if golden_record and golden_record.output is not None:
            golden_str = json.dumps(golden_record.output, indent=2, default=str)

        prompt = EMIT_PROMPT_TEMPLATE.format(
            language=self.target_language,
            module_path=source_file.path,
            source_code=source_file.read_content(self.repo_dir),
            side_effects=(
                ", ".join(guidance.side_effects) if guidance else "none identified"
            ),
            mock_recommendations=(
                ", ".join(guidance.mock_recommendations)
                if guidance
                else "none identified"
            ),
            nondeterminism_notes=(
                guidance.nondeterminism_notes if guidance else "none identified"
            ),
            golden_output=golden_str,
        )

        response = self.llm_client.generate(prompt)

        # 清除 markdown code fence
        content = response.strip()
        if content.startswith("```"):
            first_newline = content.index("\n")
            content = content[first_newline + 1 :]
        if content.endswith("```"):
            content = content[:-3].strip()

        test_path = self._derive_test_path(source_file.path)
        return EmittedTestFile(
            path=test_path,
            language=self.target_language,
            content=content,
            source_file=source_file.path,
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
