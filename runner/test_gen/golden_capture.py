"""Phase 3b：執行舊程式碼，捕獲 golden output。

對每筆 TestInput，在舊程式碼環境中執行對應函式，
記錄其輸出作為重構後的「標準答案」。

當有 LLM client 時，會生成完整的可執行腳本，
處理 class 實例化、依賴 mock、正確的呼叫方式。
沒有 LLM 時，使用簡單的 module-level 呼叫模板。
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.test_types import (
    GoldenRecord,
    GoldenSnapshot,
    TestGuidance,
    TestGuidanceIndex,
    TestInput,
)

CAPTURE_SCRIPT_PROMPT: str = """\
You are a senior test engineer. Generate a standalone Python script that:
1. Imports the target function/class from the source file
2. Sets up any necessary mocks for non-deterministic dependencies
   (random, time, network, etc.)
3. Calls the target function with the given arguments
4. Prints ONLY the return value as a single-line JSON to stdout

Context:
- File path: {module_path}
- Function/method: {function_name}
- Signature: {signature}
- Arguments: {args_json}
- Source code:
```
{source_code}
```

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- The script must be self-contained and runnable with `python script.py`
- Use `from unittest.mock import patch` if mocking is needed
- For class methods, instantiate the class first
- For properties, access them as attributes (do NOT call them)
- The LAST line must be: print(json.dumps(result, default=str))
- Do NOT include markdown code fences, return raw Python code only
- Do NOT print anything else to stdout (no debug prints, no extra output)
"""


@dataclass
class GoldenCaptureRunner:
    """在舊程式碼上執行測試輸入並捕獲輸出。

    當 ``llm_client`` 可用時，使用 LLM 生成智慧呼叫腳本，
    能處理 class method、mock 副作用依賴等情況。
    無 LLM 時退回簡單模板。

    Args:
        repo_dir: 舊程式碼（snapshot）的 repo 目錄。
        logs_dir: 執行日誌輸出目錄。
        llm_client: LLM 呼叫介面，None 表示使用 fallback。
        guidance_index: 測試指引索引，提供 mock 建議。
        timeout_sec: 單筆測試的超時秒數。
    """

    repo_dir: Path
    logs_dir: Path
    llm_client: Any = None
    guidance_index: TestGuidanceIndex | None = None
    timeout_sec: int = 30

    def run(self, inputs: list[TestInput]) -> GoldenSnapshot:
        """執行所有測試輸入並收集 golden output。

        Args:
            inputs: 測試輸入清單。

        Returns:
            GoldenSnapshot，包含所有執行結果。
        """
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        records: list[GoldenRecord] = []

        for test_input in inputs:
            record = self._capture_one(test_input)
            records.append(record)

        return GoldenSnapshot(records=records)

    def _capture_one(self, test_input: TestInput) -> GoldenRecord:
        """執行單筆測試輸入並捕獲結果。

        Args:
            test_input: 單筆測試輸入。

        Returns:
            GoldenRecord。
        """
        script = self._generate_script(test_input)

        # 將腳本寫入暫存檔再執行
        script_path = self.logs_dir / f"{test_input.input_id}_script.py"
        script_path.write_text(script, encoding="utf-8")

        start = time.monotonic()
        try:
            result = subprocess.run(
                ["python", str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                cwd=str(self.repo_dir),
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            # 寫入日誌
            log_path = self.logs_dir / f"{test_input.input_id}.log"
            log_path.write_text(
                f"script:\n{script}\n\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}",
                encoding="utf-8",
            )

            return GoldenRecord(
                input_id=test_input.input_id,
                entry_id=test_input.entry_id,
                output=self._try_parse_json(result.stdout),
                exit_code=result.returncode,
                stderr_snippet=result.stderr[:500] if result.stderr else None,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return GoldenRecord(
                input_id=test_input.input_id,
                entry_id=test_input.entry_id,
                output=None,
                exit_code=-1,
                stderr_snippet="TIMEOUT",
                duration_ms=self.timeout_sec * 1000,
            )
        except Exception as exc:
            return GoldenRecord(
                input_id=test_input.input_id,
                entry_id=test_input.entry_id,
                output=None,
                exit_code=-1,
                stderr_snippet=str(exc)[:500],
            )

    def _generate_script(self, test_input: TestInput) -> str:
        """生成可執行的 Python 腳本。

        有 LLM 時使用 LLM 生成（能處理 class method、mock 等），
        無 LLM 時使用簡單模板。

        Args:
            test_input: 測試輸入。

        Returns:
            Python 腳本字串。
        """
        parts = test_input.entry_id.split("::")
        module_path = parts[0] if len(parts) > 1 else parts[0]
        func_name = parts[1] if len(parts) > 1 else "main"

        if self.llm_client is not None:
            return self._generate_with_llm(test_input, module_path, func_name)

        return self._generate_fallback(test_input, module_path, func_name)

    def _generate_with_llm(
        self,
        test_input: TestInput,
        module_path: str,
        func_name: str,
    ) -> str:
        """用 LLM 生成智慧呼叫腳本。

        會讀取原始碼和 guidance 一起餵給 LLM，
        讓它生成能正確處理 class、mock、依賴的腳本。

        Args:
            test_input: 測試輸入。
            module_path: 原始碼檔案路徑。
            func_name: 目標函式名稱。

        Returns:
            LLM 生成的 Python 腳本。
        """
        # 讀取原始碼
        source_path = self.repo_dir / module_path
        source_code = ""
        if source_path.is_file():
            source_code = source_path.read_text(encoding="utf-8", errors="replace")

        # 取得此模組的 guidance
        guidance = self._get_guidance(module_path)

        prompt = CAPTURE_SCRIPT_PROMPT.format(
            module_path=module_path,
            function_name=func_name,
            signature="(see source code)",
            args_json=json.dumps(test_input.args),
            source_code=source_code,
            side_effects=", ".join(guidance.side_effects) if guidance else "none",
            mock_recommendations=(
                ", ".join(guidance.mock_recommendations) if guidance else "none"
            ),
            nondeterminism_notes=(
                guidance.nondeterminism_notes if guidance else "none"
            ),
        )

        response = self.llm_client.generate(prompt)

        # 清除 LLM 可能附帶的 markdown code fence
        script = response.strip()
        if script.startswith("```python"):
            script = script[len("```python") :].strip()
        if script.startswith("```"):
            script = script[3:].strip()
        if script.endswith("```"):
            script = script[:-3].strip()
        return script

    def _generate_fallback(
        self,
        test_input: TestInput,
        module_path: str,
        func_name: str,
    ) -> str:
        """無 LLM 時的簡單 fallback 腳本。

        僅支援 module-level function，不支援 class method。

        Args:
            test_input: 測試輸入。
            module_path: 原始碼檔案路徑。
            func_name: 目標函式名稱。

        Returns:
            簡單的 Python 腳本。
        """
        args_json = json.dumps(test_input.args)
        return (
            "import json\n"
            "import importlib.util\n"
            "\n"
            f"spec = importlib.util.spec_from_file_location('mod', '{module_path}')\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "\n"
            f"args = json.loads('{args_json}')\n"
            f"result = getattr(mod, '{func_name}')(**args)\n"
            "print(json.dumps(result, default=str))\n"
        )

    def _get_guidance(self, module_path: str) -> TestGuidance | None:
        """查找模組的測試指引。

        Args:
            module_path: 模組檔案路徑。

        Returns:
            TestGuidance 或 None。
        """
        if self.guidance_index is None:
            return None
        for g in self.guidance_index.guidances:
            if g.module_path == module_path:
                return g
        return None

    def _try_parse_json(self, text: str) -> str | dict | list | None:
        """嘗試將 stdout 解析為 JSON。

        優先取最後一行（LLM 腳本應在最後一行 print 結果）。

        Args:
            text: stdout 文字。

        Returns:
            解析後的物件或原始字串。
        """
        text = text.strip()
        if not text:
            return None
        # 取最後一行（LLM 腳本的 print 結果在最後）
        last_line = text.split("\n")[-1].strip()
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
