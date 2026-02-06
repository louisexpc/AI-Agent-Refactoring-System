"""LLM Review Generator：對重構結果進行語意分析與風險評估。

讀取新舊原始碼 + 測試結果，由 LLM 生成 review.json 的內容，包含：
- Semantic diff（行為差異分析，per-module）
- 風險警告（severity + tested_by_golden，per-module）
- Per-test-item 點評（test_purpose + result_analysis + failures_ignorable）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.test_gen.system_prompts import SYSTEM_REVIEW
from shared.test_types import (
    CharacterizationRecord,
    ModuleReview,
    Review,
    RiskSeverity,
    RiskWarning,
    SourceFile,
    TestItemReview,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User Prompt Template (Task-specific)
# ---------------------------------------------------------------------------

USER_REVIEW_PROMPT: str = """\
Compare the old and new code, and evaluate the test results.

Old code (before refactoring):
{old_source}

New code (after refactoring):
{new_source}

Golden output (expected behavior captured from old code):
{golden_output}

Test results summary:
- Total: {total}, Passed: {passed}, Failed: {failed}, Errored: {errored}
- Exit code: {exit_code}

Per-test results (with failure reasons if available):
{test_items_text}

Return your analysis as JSON (do NOT include markdown code fences):
{{
  "semantic_diff": "A SINGLE STRING describing behavioral differences \
between old and new code. If identical, write 'Behavior is identical.' \
Do NOT return a nested object.",
  "risk_warnings": [
    {{
      "description": "A specific risk or behavioral change",
      "severity": "low|medium|high|critical",
      "tested_by_golden": true or false
    }}
  ],
  "test_item_reviews": [
    {{
      "test_name": "exact test function name from the list above",
      "test_purpose": "What this specific test verifies",
      "result_analysis": "Why this test passed/failed/errored",
      "failures_ignorable": true or false,
      "ignorable_reason": "If failures_ignorable is true, explain why. \
Otherwise null."
    }}
  ]
}}

IMPORTANT: You MUST include a review for EVERY test item listed above.
"""


def _strip_markdown_fences(text: str) -> str:
    """移除 LLM 回應中的 markdown code fence。"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


_SEVERITY_MAP: dict[str, RiskSeverity] = {
    "low": RiskSeverity.LOW,
    "medium": RiskSeverity.MEDIUM,
    "high": RiskSeverity.HIGH,
    "critical": RiskSeverity.CRITICAL,
}


@dataclass
class ReviewGenerator:
    """LLM 驅動的重構 review 生成器。

    Attributes:
        llm_client: LLM 呼叫介面。
        repo_dir: 舊程式碼的 repo 目錄。
        refactored_repo_dir: 重構後程式碼目錄。
    """

    llm_client: Any
    repo_dir: Path
    refactored_repo_dir: Path

    def generate_review(
        self,
        run_id: str,
        records: list[CharacterizationRecord],
    ) -> Review:
        """為所有 module mappings 生成 LLM review。

        Args:
            run_id: 所屬 run 的識別碼。
            records: 每組 module mapping 的 characterization test 結果。

        Returns:
            Review model。
        """
        module_reviews: list[ModuleReview] = []
        for rec in records:
            review = self._review_single_module(rec)
            module_reviews.append(review)

        overall = self._generate_overall_assessment(module_reviews)

        return Review(
            run_id=run_id,
            modules=module_reviews,
            overall_assessment=overall,
        )

    def _review_single_module(
        self,
        rec: CharacterizationRecord,
    ) -> ModuleReview:
        """對單一 module mapping 做 LLM review。

        Args:
            rec: CharacterizationRecord。

        Returns:
            ModuleReview。
        """
        before_files = rec.module_mapping.before_files
        after_files = rec.module_mapping.after_files

        # 讀取新舊原始碼
        old_source = self._read_sources(before_files, self.repo_dir)
        new_source = self._read_sources(after_files, self.refactored_repo_dir)

        # 組裝 golden output
        golden_output = {}
        if rec.golden_records:
            for gr in rec.golden_records:
                if isinstance(gr.output, dict):
                    golden_output.update(gr.output)

        # 組裝 test results（含 failure_reason）
        total = passed = failed = errored = 0
        exit_code = None
        test_items_text = "No test results available."
        if rec.test_result:
            total = rec.test_result.total
            passed = rec.test_result.passed
            failed = rec.test_result.failed
            errored = rec.test_result.errored
            exit_code = rec.test_result.exit_code
            if rec.test_result.test_items:
                lines = []
                for item in rec.test_result.test_items:
                    line = f"  - {item.test_name}: {item.status.value}"
                    if item.failure_reason:
                        line += f" ({item.failure_reason})"
                    lines.append(line)
                test_items_text = "\n".join(lines)

        prompt = USER_REVIEW_PROMPT.format(
            old_source=old_source[:8000],
            new_source=new_source[:8000],
            golden_output=json.dumps(golden_output, indent=2, default=str)[:4000],
            total=total,
            passed=passed,
            failed=failed,
            errored=errored,
            exit_code=exit_code,
            test_items_text=test_items_text,
        )

        response = self.llm_client.generate(prompt, system_override=SYSTEM_REVIEW)
        review = self._parse_response(before_files, after_files, response)

        # 加入 source_analysis（如果有的話）
        review.source_analysis = rec.source_analysis

        return review

    def _generate_overall_assessment(
        self,
        modules: list[ModuleReview],
    ) -> str:
        """跨模組總體評估。

        Args:
            modules: 所有 module 的 review。

        Returns:
            總體評估文字。
        """
        if not modules:
            return "No modules to assess."

        # 統計風險
        high_risks = sum(
            1
            for m in modules
            for w in m.risk_warnings
            if w.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)
        )
        # 從 per-test-item reviews 判斷是否所有失敗都可忽略
        all_ignorable = all(
            all(
                tr.failures_ignorable
                for tr in m.test_item_reviews
                if tr.failures_ignorable is not None
            )
            or not m.test_item_reviews
            for m in modules
        )

        if high_risks == 0 and all_ignorable:
            return (
                f"Reviewed {len(modules)} module(s). "
                "No high-severity risks detected. "
                "All test results are consistent or failures are ignorable."
            )

        return (
            f"Reviewed {len(modules)} module(s). "
            f"Found {high_risks} high/critical risk warning(s). "
            "Manual review recommended for flagged items."
        )

    def _read_sources(self, file_paths: list[str], repo_dir: Path) -> str:
        """讀取並聚合原始碼。

        Args:
            file_paths: 檔案路徑清單。
            repo_dir: repo 根目錄。

        Returns:
            聚合後的原始碼字串。
        """
        sections: list[str] = []
        for fp in file_paths:
            sf = SourceFile(path=fp, lang="")
            try:
                content = sf.read_content(repo_dir)
                sections.append(f"--- {fp} ---\n{content}")
            except FileNotFoundError:
                sections.append(f"--- {fp} ---\n[FILE NOT FOUND]")
        return "\n\n".join(sections)

    def _parse_response(
        self,
        before_files: list[str],
        after_files: list[str],
        response: str,
    ) -> ModuleReview:
        """解析 LLM 回應為 ModuleReview。

        Args:
            before_files: 舊 repo 的檔案路徑清單。
            after_files: 新 repo 的檔案路徑清單。
            response: LLM 回應文字。

        Returns:
            ModuleReview。
        """
        cleaned = _strip_markdown_fences(response)
        try:
            data = json.loads(cleaned)
            return ModuleReview(
                before_files=before_files,
                after_files=after_files,
                semantic_diff=data.get("semantic_diff", ""),
                risk_warnings=self._parse_warnings(data.get("risk_warnings", [])),
                test_item_reviews=self._parse_test_item_reviews(
                    data.get("test_item_reviews", [])
                ),
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to parse review for %s: %s", before_files, exc)
            return ModuleReview(
                before_files=before_files,
                after_files=after_files,
                semantic_diff="[LLM parse failure]",
            )

    def _parse_warnings(self, raw: list[dict]) -> list[RiskWarning]:
        """解析 risk_warnings 清單。

        Args:
            raw: LLM 回傳的 raw dict list。

        Returns:
            RiskWarning 清單。
        """
        warnings: list[RiskWarning] = []
        if not isinstance(raw, list):
            return warnings
        for item in raw:
            if not isinstance(item, dict):
                continue
            severity_str = str(item.get("severity", "low")).lower()
            warnings.append(
                RiskWarning(
                    description=item.get("description", ""),
                    severity=_SEVERITY_MAP.get(severity_str, RiskSeverity.LOW),
                    tested_by_golden=bool(item.get("tested_by_golden", False)),
                )
            )
        return warnings

    def _parse_test_item_reviews(self, raw: list[dict]) -> list[TestItemReview]:
        """解析 test_item_reviews 清單。

        Args:
            raw: LLM 回傳的 raw dict list。

        Returns:
            TestItemReview 清單。
        """
        reviews: list[TestItemReview] = []
        if not isinstance(raw, list):
            return reviews
        for item in raw:
            if not isinstance(item, dict):
                continue
            test_name = item.get("test_name", "")
            if not test_name:
                continue
            reviews.append(
                TestItemReview(
                    test_name=test_name,
                    test_purpose=item.get("test_purpose", ""),
                    result_analysis=item.get("result_analysis", ""),
                    failures_ignorable=bool(item.get("failures_ignorable", False)),
                    ignorable_reason=item.get("ignorable_reason"),
                )
            )
        return reviews
