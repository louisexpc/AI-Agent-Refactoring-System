"""報告建構器：彙總比較結果為 OverallTestReport。

統計 pass/fail/error/skipped 數量與通過率。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.test_types import (
    ComparisonResult,
    ComparisonVerdict,
    GoldenSnapshot,
    OverallTestReport,
)


@dataclass
class ReportBuilder:
    """彙總 golden comparison 結果為 OverallTestReport。"""

    def build(
        self,
        run_id: str,
        golden_snapshot: GoldenSnapshot,
        comparison_results: list[ComparisonResult] | None = None,
    ) -> OverallTestReport:
        """建立整體測試報告。

        Args:
            run_id: 所屬 run 的識別碼。
            golden_snapshot: golden baseline 記錄。
            comparison_results: 比較結果清單（迭代時才有）。

        Returns:
            OverallTestReport。
        """
        results = comparison_results or []
        if results:
            passed = sum(1 for r in results if r.verdict == ComparisonVerdict.PASS)
            total = len(results)
            pass_rate = passed / total if total > 0 else 0.0
        else:
            pass_rate = 0.0

        return OverallTestReport(
            run_id=run_id,
            golden_snapshot=golden_snapshot,
            comparison_results=results,
            pass_rate=round(pass_rate, 4),
        )
