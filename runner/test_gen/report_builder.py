"""Stage Report Builder：彙總 CharacterizationRecord 為 StageTestReport。

統計 overall pass rate 與 coverage。
"""

from __future__ import annotations

from shared.test_types import CharacterizationRecord, StageTestReport


def build_stage_report(
    run_id: str,
    records: list[CharacterizationRecord],
    build_success: bool | None = None,
) -> StageTestReport:
    """建立 Stage 測試報告。

    Args:
        run_id: 所屬 run 的識別碼。
        records: 每組 module mapping 的 characterization test 結果。
        build_success: 新 code 是否能成功 build。

    Returns:
        StageTestReport。
    """
    total_passed = 0
    total_tests = 0
    coverage_values: list[float] = []

    for rec in records:
        if rec.test_result is not None:
            total_passed += rec.test_result.passed
            total_tests += rec.test_result.total
        if rec.coverage_pct is not None:
            coverage_values.append(rec.coverage_pct)

    overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0.0
    overall_coverage = (
        round(sum(coverage_values) / len(coverage_values), 2)
        if coverage_values
        else None
    )

    return StageTestReport(
        run_id=run_id,
        records=records,
        overall_pass_rate=round(overall_pass_rate, 4),
        overall_coverage_pct=overall_coverage,
        build_success=build_success,
    )


def build_summary(report: StageTestReport) -> dict:
    """建立精簡的 summary dict。

    Args:
        report: StageTestReport。

    Returns:
        精簡的 summary dict。
    """
    total_passed = 0
    total_failed = 0
    total_errored = 0

    for rec in report.records:
        if rec.test_result is not None:
            total_passed += rec.test_result.passed
            total_failed += rec.test_result.failed
            total_errored += rec.test_result.errored

    return {
        "run_id": report.run_id,
        "build_success": report.build_success,
        "overall_pass_rate": report.overall_pass_rate,
        "overall_coverage_pct": report.overall_coverage_pct,
        "total_modules": len(report.records),
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errored": total_errored,
    }
