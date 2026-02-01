"""Generate Test 模組。

提供測試生成 pipeline 的公開介面：
- ``run_overall_test``: 建立 golden baseline / 執行 golden comparison。
- ``run_module_test``: 針對單一 module 生成 + 執行 unit test。
"""

from __future__ import annotations

from runner.test_gen.main import run_module_test, run_overall_test

__all__ = ["run_module_test", "run_overall_test"]
