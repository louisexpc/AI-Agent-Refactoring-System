"""Generate Test 模組。

提供測試生成 pipeline 的公開介面：
- ``run_test_generation``: 執行完整測試生成流程。
"""

from __future__ import annotations

from runner.test_gen.main import run_test_generation

__all__ = ["run_test_generation"]
