"""Golden Comparison：比較 golden output 與重構後程式碼的輸出。

對每個來源檔案，在重構後的程式碼上執行相同的 golden 腳本，
再與 golden output 比較，判定 PASS/FAIL/ERROR/SKIPPED。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runner.test_gen.golden_capture import GoldenCaptureRunner
from runner.test_gen.output_normalizer import OutputNormalizer
from shared.test_types import (
    ComparisonResult,
    ComparisonVerdict,
    GoldenRecord,
    GoldenSnapshot,
    SourceFile,
)


@dataclass
class GoldenComparator:
    """比較重構後程式碼與 golden output 的差異。

    Args:
        refactored_repo_dir: 重構後程式碼的目錄。
        logs_dir: 執行日誌輸出目錄。
        normalizer: 輸出正規化器，用於清洗非確定性欄位。
        timeout_sec: 單筆測試的超時秒數。
    """

    refactored_repo_dir: Path
    logs_dir: Path
    normalizer: OutputNormalizer | None = None
    timeout_sec: int = 30

    def __post_init__(self) -> None:
        """初始化預設 normalizer。"""
        if self.normalizer is None:
            self.normalizer = OutputNormalizer()

    def run(
        self,
        source_files: list[SourceFile],
        golden: GoldenSnapshot,
    ) -> list[ComparisonResult]:
        """執行重構後程式碼並與 golden 比較。

        Args:
            source_files: 來源檔案清單。
            golden: 舊程式碼的 golden output。

        Returns:
            每個檔案的比較結果。
        """
        golden_map: dict[str, GoldenRecord] = {r.file_path: r for r in golden.records}

        capture = GoldenCaptureRunner(
            repo_dir=self.refactored_repo_dir,
            logs_dir=self.logs_dir / "refactored",
            timeout_sec=self.timeout_sec,
        )
        actual_snapshot = capture.run(source_files)
        actual_map: dict[str, GoldenRecord] = {
            r.file_path: r for r in actual_snapshot.records
        }

        results: list[ComparisonResult] = []
        for sf in source_files:
            expected = golden_map.get(sf.path)
            actual = actual_map.get(sf.path)
            result = self._compare_one(sf.path, expected, actual)
            results.append(result)

        return results

    def _compare_one(
        self,
        file_path: str,
        expected: GoldenRecord | None,
        actual: GoldenRecord | None,
    ) -> ComparisonResult:
        """比較單筆測試結果。

        Args:
            file_path: 檔案路徑。
            expected: golden（舊）的輸出。
            actual: 重構後（新）的輸出。

        Returns:
            比較結果。
        """
        if expected is None:
            return ComparisonResult(
                file_path=file_path,
                verdict=ComparisonVerdict.SKIPPED,
                diff_summary="no golden record found",
            )

        if actual is None:
            return ComparisonResult(
                file_path=file_path,
                verdict=ComparisonVerdict.ERROR,
                expected_output=expected.output,
                diff_summary="no actual output captured",
            )

        if actual.exit_code != 0 and expected.exit_code == 0:
            return ComparisonResult(
                file_path=file_path,
                verdict=ComparisonVerdict.ERROR,
                expected_output=expected.output,
                actual_output=actual.output,
                diff_summary=(
                    f"exit code mismatch: expected 0, got {actual.exit_code}"
                ),
            )

        assert self.normalizer is not None
        norm_expected = self.normalizer.normalize(expected.output)
        norm_actual = self.normalizer.normalize(actual.output)

        if norm_expected == norm_actual:
            verdict = ComparisonVerdict.PASS
            diff_summary = None
        else:
            verdict = ComparisonVerdict.FAIL
            diff_summary = self._build_diff_summary(norm_expected, norm_actual)

        return ComparisonResult(
            file_path=file_path,
            verdict=verdict,
            expected_output=expected.output,
            actual_output=actual.output,
            diff_summary=diff_summary,
        )

    def _build_diff_summary(self, expected: str, actual: str) -> str:
        """建立簡短的差異摘要。

        Args:
            expected: 正規化後的預期輸出。
            actual: 正規化後的實際輸出。

        Returns:
            差異摘要字串。
        """
        max_len = 200
        exp_short = expected[:max_len] + ("..." if len(expected) > max_len else "")
        act_short = actual[:max_len] + ("..." if len(actual) > max_len else "")
        return f"expected: {exp_short}\nactual: {act_short}"
