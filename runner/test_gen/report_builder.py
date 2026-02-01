"""Phase 4b：彙總比較結果為測試報告。

統計 pass/fail/error/skipped 數量與通過率，
產出 TestReport 供下游 Report 模組與 Fallback 判斷使用。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.test_types import (
    ComparisonResult,
    ComparisonVerdict,
    EmittedTestFile,
    TestReport,
)


@dataclass
class TestReportBuilder:
    """彙總比較結果為 TestReport。"""

    def build(
        self,
        run_id: str,
        iteration: int,
        results: list[ComparisonResult],
        emitted_files: list[EmittedTestFile] | None = None,
        coverage_pct: float | None = None,
    ) -> TestReport:
        """建立測試報告。

        Args:
            run_id: 所屬 run 的識別碼。
            iteration: 迭代輪次。
            results: 比較結果清單。
            emitted_files: 產出的測試檔案清單。
            coverage_pct: 行覆蓋率百分比（若有）。

        Returns:
            TestReport。
        """
        passed = sum(1 for r in results if r.verdict == ComparisonVerdict.PASS)
        failed = sum(1 for r in results if r.verdict == ComparisonVerdict.FAIL)
        errored = sum(1 for r in results if r.verdict == ComparisonVerdict.ERROR)
        skipped = sum(1 for r in results if r.verdict == ComparisonVerdict.SKIPPED)
        total = len(results)
        pass_rate = passed / total if total > 0 else 0.0

        return TestReport(
            run_id=run_id,
            iteration=iteration,
            total=total,
            passed=passed,
            failed=failed,
            errored=errored,
            skipped=skipped,
            pass_rate=round(pass_rate, 4),
            coverage_pct=coverage_pct,
            results=results,
            emitted_files=emitted_files or [],
        )
