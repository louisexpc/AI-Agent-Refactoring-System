"""Generate Test 模組。

提供測試生成 pipeline 的公開介面：
- ``run_characterization_test``: 單一 module mapping 的 characterization test。
- ``run_stage_test``: 整個 Stage 的測試。
"""

from __future__ import annotations

from runner.test_gen.main import run_characterization_test, run_stage_test

__all__ = ["run_characterization_test", "run_stage_test"]
