"""Generate Test 模組的型別定義。

定義測試生成流程中所有階段的資料模型，包含：
- 來源檔案識別
- LLM 測試指引
- Golden output 記錄與比較
- 單元測試結果與報告
"""

from __future__ import annotations

import json as _json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Source File（Phase 1: File Filter 輸出）
# ---------------------------------------------------------------------------


class SourceFile(BaseModel):
    """從 DepGraph 過濾後的來源檔案。

    Attributes:
        path: 檔案相對路徑（相對於 repo root）。
        lang: 語言識別（python, go, javascript, typescript）。
    """

    path: str
    lang: str

    def read_content(self, repo_dir: Any) -> str:
        """從磁碟讀取檔案內容。

        Args:
            repo_dir: repo 根目錄（Path 或 str）。

        Returns:
            檔案完整原始碼。
        """
        from pathlib import Path as _Path

        return (_Path(repo_dir) / self.path).read_text(
            encoding="utf-8", errors="replace"
        )


# ---------------------------------------------------------------------------
# Guidance（Phase 2: LLM 測試指引）
# ---------------------------------------------------------------------------


class TestGuidance(BaseModel):
    """LLM 針對單一模組產生的測試指引。

    描述該模組在測試時需注意的副作用、mock 建議及非確定性行為。

    Attributes:
        module_path: 模組檔案路徑。
        side_effects: 識別出的副作用類型，如 ``file I/O``、``network``。
        mock_recommendations: 建議 mock 的依賴或函式。
        nondeterminism_notes: 非確定性行為說明（時間戳、隨機數等）。
        external_deps: 外部依賴清單（API、DB 等）。
    """

    module_path: str
    side_effects: list[str] = Field(default_factory=list)
    mock_recommendations: list[str] = Field(default_factory=list)
    nondeterminism_notes: str | None = None
    external_deps: list[str] = Field(default_factory=list)

    @field_validator(
        "side_effects", "mock_recommendations", "external_deps", mode="before"
    )
    @classmethod
    def _coerce_none_to_list(cls, v: Any) -> list[str]:
        """LLM 可能回傳 null、字串或 list[dict]，統一轉為 list[str]。"""
        if v is None:
            return []
        if isinstance(v, str):
            if v.strip().lower() == "null":
                return []
            return [v]
        if isinstance(v, list):
            return [
                item if isinstance(item, str) else _json.dumps(item, ensure_ascii=False)
                for item in v
            ]
        return v


class TestGuidanceIndex(BaseModel):
    """所有模組的測試指引索引。"""

    guidances: list[TestGuidance] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Golden Record（Phase 3: Golden Capture 輸出）
# ---------------------------------------------------------------------------


class GoldenRecord(BaseModel):
    """舊程式碼對某個檔案的執行結果（標準答案）。

    Attributes:
        file_path: 來源檔案路徑。
        output: 捕獲的輸出（stdout 序列化）。
        exit_code: 程式結束碼。
        stderr_snippet: stderr 片段。
        duration_ms: 執行時間（毫秒）。
    """

    file_path: str
    output: Any = None
    exit_code: int | None = None
    stderr_snippet: str | None = None
    duration_ms: int | None = None
    coverage_pct: float | None = None


class GoldenSnapshot(BaseModel):
    """所有 golden record 的集合。"""

    records: list[GoldenRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Golden Comparison（Phase 6 / 迭代時）
# ---------------------------------------------------------------------------


class ComparisonVerdict(str, Enum):
    """單筆測試比較的判定結果。"""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


class ComparisonResult(BaseModel):
    """新舊程式碼單筆輸出的比較結果。

    Attributes:
        file_path: 來源檔案路徑。
        verdict: 判定結果。
        expected_output: golden（舊）的輸出。
        actual_output: 重構後（新）的輸出。
        diff_summary: 差異摘要。
    """

    file_path: str
    verdict: ComparisonVerdict
    expected_output: Any = None
    actual_output: Any = None
    diff_summary: str | None = None


# ---------------------------------------------------------------------------
# Emitted Test File（Phase 4: Test Emitter 輸出）
# ---------------------------------------------------------------------------


class EmittedTestFile(BaseModel):
    """產出的可執行測試原始碼檔案。

    Attributes:
        path: 測試檔案相對路徑。
        language: 目標語言（python、go、typescript 等）。
        content: 測試原始碼內容。
        source_file: 對應的來源檔案路徑。
    """

    path: str
    language: str
    content: str
    source_file: str


# ---------------------------------------------------------------------------
# Unit Test Result（Phase 5: Test Runner 輸出）
# ---------------------------------------------------------------------------


class TestItemStatus(str, Enum):
    """個別 test function 的執行結果。"""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class TestItemResult(BaseModel):
    """單一 test function 的結果（從 pytest -v 解析）。

    Attributes:
        test_name: 測試函式名稱（例如 ``test_driver_instantiation``）。
        status: 通過/失敗/錯誤/跳過。
        failure_reason: 失敗或錯誤時的簡短原因（從 pytest short summary 解析）。
    """

    test_name: str
    status: TestItemStatus
    failure_reason: str | None = None


class UnitTestResult(BaseModel):
    """單一 emitted test file 的執行結果。

    Attributes:
        test_file: 測試檔案路徑。
        total: 測試案例總數。
        passed: 通過數。
        failed: 失敗數。
        errored: 錯誤數。
        coverage_pct: 該檔案的行覆蓋率。
        stdout: pytest stdout 摘要。
        stderr: pytest stderr 摘要。
        exit_code: pytest 結束碼。
        test_items: 個別 test function 的結果清單。
    """

    test_file: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    coverage_pct: float | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    test_items: list[TestItemResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reports（API 輸出）
# ---------------------------------------------------------------------------


class ModuleMapping(BaseModel):
    """Stage Plan 裡的一組 before/after 檔案對應。

    Attributes:
        before_files: 舊 repo 的檔案路徑清單（相對於 repo root）。
        after_files: 新 repo 的檔案路徑清單（相對於 refactored repo root）。
    """

    before_files: list[str]
    after_files: list[str]


class CharacterizationRecord(BaseModel):
    """單一 module mapping 的 characterization test 結果。

    Attributes:
        module_mapping: 對應的 before/after 檔案映射。
        golden_records: 舊 code 的 golden output。
        emitted_test_file: LLM 生成的目標語言 test file。
        test_result: test file 的執行結果。
        coverage_pct: 行覆蓋率。
        tested_functions: LLM 決定測試的功能名稱（golden output keys）。
        golden_script_path: golden capture 腳本的相對路徑。
        emitted_test_path: 生成的 test file 的相對路徑。
        source_analysis: 原始碼編譯分析結果（如果執行了檢查）。
    """

    module_mapping: ModuleMapping
    golden_records: list[GoldenRecord] = Field(default_factory=list)
    emitted_test_file: EmittedTestFile | None = None
    test_result: UnitTestResult | None = None
    coverage_pct: float | None = None
    tested_functions: list[str] = Field(default_factory=list)
    golden_script_path: str | None = None
    emitted_test_path: str | None = None
    source_analysis: SourceAnalysis | None = None


class StageTestReport(BaseModel):
    """一個 Stage 的完整測試報告（in-memory 用，不再直接寫檔）。

    Attributes:
        run_id: 所屬 run 的識別碼。
        records: 每組 module mapping 的 characterization test 結果。
        overall_pass_rate: 所有 test 的通過率（0.0 ~ 1.0）。
        overall_coverage_pct: 平均行覆蓋率。
        build_success: 新 code 是否能成功 build。
        build_error: build 失敗時的錯誤訊息。
    """

    run_id: str
    records: list[CharacterizationRecord] = Field(default_factory=list)
    overall_pass_rate: float = 0.0
    overall_coverage_pct: float | None = None
    build_success: bool | None = None
    build_error: str | None = None


# ---------------------------------------------------------------------------
# summary.json model
# ---------------------------------------------------------------------------


class StageSummary(BaseModel):
    """summary.json 的資料模型。

    Attributes:
        run_id: 所屬 run 的識別碼。
        build_success: 新 code 是否能成功 build。
        build_error: build 失敗時的錯誤訊息。
        overall_pass_rate: 所有 test 的通過率。
        overall_coverage_pct: 平均行覆蓋率。
        total_modules: 測試的 module 數量。
        total_passed: 通過的 test 數量。
        total_failed: 失敗的 test 數量。
        total_errored: 錯誤的 test 數量。
    """

    run_id: str
    build_success: bool | None = None
    build_error: str | None = None
    overall_pass_rate: float = 0.0
    overall_coverage_pct: float | None = None
    total_modules: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_errored: int = 0


# ---------------------------------------------------------------------------
# test_records.json models
# ---------------------------------------------------------------------------


class ModuleTestRecord(BaseModel):
    """單一 module 的事實記錄（純資料，無 LLM 分析）。

    Attributes:
        before_files: 舊 repo 的檔案路徑清單。
        after_files: 新 repo 的檔案路徑清單。
        golden_output: 舊 code 的 golden output dict。
        golden_exit_code: golden capture script 的 exit code。
        golden_coverage_pct: golden capture 的覆蓋率。
        tested_functions: golden output 的 keys 清單。
        test_file_path: 生成的測試檔相對路徑。
        golden_script_path: golden capture 腳本相對路徑。
        test_items: 個別 test function 的結果。
        aggregate_passed: 通過數。
        aggregate_failed: 失敗數。
        aggregate_errored: 錯誤數。
        coverage_pct: 測試覆蓋率。
        test_exit_code: pytest exit code。
    """

    before_files: list[str]
    after_files: list[str]
    golden_output: Any = None
    golden_exit_code: int | None = None
    golden_coverage_pct: float | None = None
    tested_functions: list[str] = Field(default_factory=list)
    test_file_path: str | None = None
    golden_script_path: str | None = None
    test_items: list[TestItemResult] = Field(default_factory=list)
    aggregate_passed: int = 0
    aggregate_failed: int = 0
    aggregate_errored: int = 0
    coverage_pct: float | None = None
    test_exit_code: int | None = None


class TestRecords(BaseModel):
    """test_records.json 的 root model。

    Attributes:
        run_id: 所屬 run 的識別碼。
        modules: 每個 module 的事實記錄。
    """

    run_id: str
    modules: list[ModuleTestRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# review.json models
# ---------------------------------------------------------------------------


class SourceIssueSeverity(str, Enum):
    """原始碼問題嚴重程度。"""

    SAFE_TO_FIX = "safe_to_fix"  # 可自動修復且不改變語意（例如 unused imports）
    WARNING = "warning"  # 小問題，可能不影響執行
    CRITICAL = "critical"  # 阻止編譯或執行的問題


class SourceIssue(BaseModel):
    """原始碼編譯或語法問題。

    Attributes:
        issue_type: 問題類型（unused_import, syntax_error, missing_dependency 等）。
        severity: 嚴重程度。
        description: 問題描述。
        file_path: 發生問題的檔案路徑。
        line_number: 行號（如果可解析）。
        suggested_fix: 建議的修復方式（如果 severity 是 safe_to_fix）。
    """

    issue_type: str
    severity: SourceIssueSeverity
    description: str
    file_path: str
    line_number: int | None = None
    suggested_fix: str | None = None


class SourceAnalysis(BaseModel):
    """原始碼分析結果。

    Attributes:
        compilable: 原始碼是否可編譯。
        issues: 發現的問題清單。
        auto_fixed: 已自動修復的問題清單。
        error_output: 編譯器或語法檢查器的錯誤輸出。
    """

    compilable: bool
    issues: list[SourceIssue] = Field(default_factory=list)
    auto_fixed: list[SourceIssue] = Field(default_factory=list)
    error_output: str | None = None


class RiskSeverity(str, Enum):
    """風險嚴重程度。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskWarning(BaseModel):
    """LLM 識別的風險項。

    Attributes:
        description: 風險描述。
        severity: 嚴重程度。
        tested_by_golden: 是否已被 golden test 覆蓋。
    """

    description: str
    severity: RiskSeverity
    tested_by_golden: bool = False


class TestItemReview(BaseModel):
    """單一 test function 的 LLM 點評。

    Attributes:
        test_name: 測試函式名稱。
        test_purpose: 該測試的目的說明。
        result_analysis: 測試結果分析（通過/失敗原因）。
        failures_ignorable: 失敗是否可忽略。
        ignorable_reason: 可忽略的原因。
    """

    test_name: str
    test_purpose: str = ""
    result_analysis: str = ""
    failures_ignorable: bool = False
    ignorable_reason: str | None = None


class ModuleReview(BaseModel):
    """單一 module 的 LLM 點評。

    Attributes:
        before_files: 舊 repo 的檔案路徑清單。
        after_files: 新 repo 的檔案路徑清單。
        semantic_diff: 新舊 code 的行為差異分析。
        risk_warnings: 風險清單。
        test_item_reviews: 每個 test function 的 LLM 點評。
        source_analysis: 原始碼編譯分析結果（如果執行了檢查）。
    """

    before_files: list[str]
    after_files: list[str]
    semantic_diff: str = ""
    risk_warnings: list[RiskWarning] = Field(default_factory=list)
    test_item_reviews: list[TestItemReview] = Field(default_factory=list)
    source_analysis: SourceAnalysis | None = None

    @field_validator("semantic_diff", mode="before")
    @classmethod
    def _coerce_semantic_diff(cls, v: Any) -> str:
        """LLM 可能回傳 dict 而非 string，統一轉為 str。"""
        if v is None:
            return ""
        if isinstance(v, dict):
            # LLM 回傳了結構化物件，轉為 JSON 字串
            return _json.dumps(v, ensure_ascii=False)
        return str(v)


class Review(BaseModel):
    """review.json 的 root model。

    Attributes:
        run_id: 所屬 run 的識別碼。
        modules: 每個 module 的 LLM 點評。
        overall_assessment: 跨模組的總體評估。
    """

    run_id: str
    modules: list[ModuleReview] = Field(default_factory=list)
    overall_assessment: str | None = None
