"""Stage Report Builder：彙總 CharacterizationRecord 為各種輸出格式。

產出三個檔案的資料模型：
- summary.json  → StageSummary
- test_records.json → TestRecords
- StageTestReport（in-memory 用）
"""

from __future__ import annotations

from shared.test_types import (
    CharacterizationRecord,
    ModuleTestRecord,
    StageSummary,
    StageTestReport,
    TestRecords,
)


def build_stage_report(
    run_id: str,
    records: list[CharacterizationRecord],
    build_success: bool | None = None,
    build_error: str | None = None,
) -> StageTestReport:
    """建立 Stage 測試報告（in-memory）。

    Args:
        run_id: 所屬 run 的識別碼。
        records: 每組 module mapping 的 characterization test 結果。
        build_success: 新 code 是否能成功 build。
        build_error: build 失敗時的錯誤訊息。

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
        build_error=build_error[:2000] if build_error else None,
    )


def build_summary(report: StageTestReport) -> StageSummary:
    """建立 summary.json 的資料模型。

    Args:
        report: StageTestReport。

    Returns:
        StageSummary。
    """
    total_passed = 0
    total_failed = 0
    total_errored = 0

    for rec in report.records:
        if rec.test_result is not None:
            total_passed += rec.test_result.passed
            total_failed += rec.test_result.failed
            total_errored += rec.test_result.errored

    return StageSummary(
        run_id=report.run_id,
        build_success=report.build_success,
        build_error=report.build_error,
        overall_pass_rate=report.overall_pass_rate,
        overall_coverage_pct=report.overall_coverage_pct,
        total_modules=len(report.records),
        total_passed=total_passed,
        total_failed=total_failed,
        total_errored=total_errored,
    )


def build_test_records(
    run_id: str,
    records: list[CharacterizationRecord],
) -> TestRecords:
    """建立 test_records.json 的資料模型（純事實，無 LLM 分析）。

    Args:
        run_id: 所屬 run 的識別碼。
        records: 每組 module mapping 的 characterization test 結果。

    Returns:
        TestRecords。
    """
    modules: list[ModuleTestRecord] = []

    for rec in records:
        golden_output = None
        golden_exit_code = None
        golden_coverage_pct = None
        if rec.golden_records:
            gr = rec.golden_records[0]
            golden_output = gr.output
            golden_exit_code = gr.exit_code
            golden_coverage_pct = gr.coverage_pct

        test_items = []
        agg_passed = agg_failed = agg_errored = 0
        cov = None
        test_exit_code = None
        if rec.test_result:
            test_items = rec.test_result.test_items
            agg_passed = rec.test_result.passed
            agg_failed = rec.test_result.failed
            agg_errored = rec.test_result.errored
            cov = rec.test_result.coverage_pct
            test_exit_code = rec.test_result.exit_code

        modules.append(
            ModuleTestRecord(
                before_files=rec.module_mapping.before_files,
                after_files=rec.module_mapping.after_files,
                golden_output=golden_output,
                golden_exit_code=golden_exit_code,
                golden_coverage_pct=golden_coverage_pct,
                tested_functions=rec.tested_functions,
                test_file_path=rec.emitted_test_path,
                golden_script_path=rec.golden_script_path,
                test_items=test_items,
                aggregate_passed=agg_passed,
                aggregate_failed=agg_failed,
                aggregate_errored=agg_errored,
                coverage_pct=cov,
                test_exit_code=test_exit_code,
            )
        )

    return TestRecords(run_id=run_id, modules=modules)
