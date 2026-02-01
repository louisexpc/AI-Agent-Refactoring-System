"""Phase 3：執行舊程式碼，捕獲 golden output（file 級別）。

對每個來源檔案，由 LLM 生成一個呼叫腳本，
在舊程式碼環境中執行並記錄輸出作為標準答案。
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
    SourceFile,
    TestGuidance,
    TestGuidanceIndex,
)

CAPTURE_SCRIPT_PROMPT: str = """\
You are a senior test engineer. Generate a standalone Python script that:
1. Imports all public functions/classes from the source file
2. Calls each public function with representative arguments
3. Prints ALL return values as a single JSON object to stdout

Context:
- File path (relative to repo root): {module_path}
- The script will be executed with cwd = repo root
- Source code:
```
{source_code}
```

Testing guidance:
- Side effects: {side_effects}
- Mock recommendations: {mock_recommendations}
- Nondeterminism notes: {nondeterminism_notes}

Requirements:
- IMPORTANT: The file's parent directory is NOT a Python package (no __init__.py).
  You MUST add the file's directory to sys.path before importing. Example:
  ```
  import sys
  sys.path.insert(0, '{module_dir}')
  from {module_name} import SomeClass
  ```
- The script must be self-contained and runnable with `python script.py`
- Use `from unittest.mock import patch` if mocking is needed
- For class methods, instantiate the class first
- Collect all results into a dict and print as JSON on the LAST line
- The LAST line must be: print(json.dumps(results, default=str))
- Do NOT include markdown code fences, return raw Python code only
- Do NOT print anything else to stdout
"""


@dataclass
class GoldenCaptureRunner:
    """在舊程式碼上執行並捕獲 golden output（file 級別）。

    每個來源檔案生成一個呼叫腳本，執行後記錄 stdout 作為 golden output。

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

    def run(self, source_files: list[SourceFile]) -> GoldenSnapshot:
        """執行所有來源檔案並收集 golden output。

        Args:
            source_files: 來源檔案清單。

        Returns:
            GoldenSnapshot，包含所有執行結果。
        """
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        records: list[GoldenRecord] = []

        for sf in source_files:
            record = self._capture_one(sf)
            records.append(record)

        return GoldenSnapshot(records=records)

    def _capture_one(self, source_file: SourceFile) -> GoldenRecord:
        """執行單一來源檔案並捕獲結果。

        Args:
            source_file: 來源檔案。

        Returns:
            GoldenRecord。
        """
        script = self._generate_script(source_file)
        safe_name = source_file.path.replace("/", "_").replace(".", "_")

        script_path = self.logs_dir / f"{safe_name}_script.py"
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

            log_path = self.logs_dir / f"{safe_name}.log"
            log_path.write_text(
                f"script:\n{script}\n\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}",
                encoding="utf-8",
            )

            return GoldenRecord(
                file_path=source_file.path,
                output=self._try_parse_json(result.stdout),
                exit_code=result.returncode,
                stderr_snippet=result.stderr[:500] if result.stderr else None,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return GoldenRecord(
                file_path=source_file.path,
                exit_code=-1,
                stderr_snippet="TIMEOUT",
                duration_ms=self.timeout_sec * 1000,
            )
        except Exception as exc:
            return GoldenRecord(
                file_path=source_file.path,
                exit_code=-1,
                stderr_snippet=str(exc)[:500],
            )

    def _generate_script(self, source_file: SourceFile) -> str:
        """生成可執行的 Python 腳本。

        Args:
            source_file: 來源檔案。

        Returns:
            Python 腳本字串。
        """
        if self.llm_client is not None:
            return self._generate_with_llm(source_file)
        return self._generate_fallback(source_file)

    def _generate_with_llm(self, source_file: SourceFile) -> str:
        """用 LLM 生成呼叫腳本。

        Args:
            source_file: 來源檔案。

        Returns:
            LLM 生成的 Python 腳本。
        """
        guidance = self._get_guidance(source_file.path)

        module_dir = str(Path(source_file.path).parent)
        module_name = Path(source_file.path).stem

        prompt = CAPTURE_SCRIPT_PROMPT.format(
            module_path=source_file.path,
            module_dir=module_dir,
            module_name=module_name,
            source_code=source_file.read_content(self.repo_dir),
            side_effects=", ".join(guidance.side_effects) if guidance else "none",
            mock_recommendations=(
                ", ".join(guidance.mock_recommendations) if guidance else "none"
            ),
            nondeterminism_notes=(
                guidance.nondeterminism_notes if guidance else "none"
            ),
        )

        response = self.llm_client.generate(prompt)

        # 清除 markdown code fence
        script = response.strip()
        if script.startswith("```python"):
            script = script[len("```python") :].strip()
        if script.startswith("```"):
            script = script[3:].strip()
        if script.endswith("```"):
            script = script[:-3].strip()
        return script

    def _generate_fallback(self, source_file: SourceFile) -> str:
        """無 LLM 時的 fallback 腳本。

        Args:
            source_file: 來源檔案。

        Returns:
            簡單的 Python 腳本。
        """
        module_dir = str(Path(source_file.path).parent)
        module_name = Path(source_file.path).stem
        return (
            "import json\n"
            "import sys\n"
            f"sys.path.insert(0, '{module_dir}')\n"
            "\n"
            f"import {module_name} as mod\n"
            "\n"
            "results = {}\n"
            "for name in dir(mod):\n"
            "    if name.startswith('_'):\n"
            "        continue\n"
            "    obj = getattr(mod, name)\n"
            "    if callable(obj):\n"
            "        try:\n"
            "            results[name] = str(obj)\n"
            "        except Exception as e:\n"
            "            results[name] = f'ERROR: {e}'\n"
            "print(json.dumps(results, default=str))\n"
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
