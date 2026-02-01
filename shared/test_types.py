"""Generate Test 模組的型別定義。

定義測試生成流程中所有階段的資料模型，包含：
- 可測試 entry point 識別
- LLM 測試指引
- 測試輸入 / golden output
- 比較結果與報告
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TestableEntry(BaseModel):
    """從 DepGraph 中識別出的可測試函式或端點。

    Attributes:
        entry_id: 唯一識別碼，格式如 ``src/auth.py::login``。
        module_path: 所屬檔案路徑。
        function_name: 函式或方法名稱。
        signature: 參數型別簽名（若可取得）。
        docstring: 函式 docstring。
        dep_node_id: 對應 DepNode 的 node_id。
    """

    entry_id: str
    module_path: str
    function_name: str
    signature: str | None = None
    docstring: str | None = None
    dep_node_id: str | None = None


class EntryIndex(BaseModel):
    """所有可測試 entry point 的索引。"""

    entries: list[TestableEntry] = Field(default_factory=list)


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


class TestGuidanceIndex(BaseModel):
    """所有模組的測試指引索引。"""

    guidances: list[TestGuidance] = Field(default_factory=list)


class TestInput(BaseModel):
    """單一測試案例的輸入資料。

    Attributes:
        input_id: 測試輸入唯一識別碼。
        entry_id: 對應的 TestableEntry entry_id。
        args: 函式呼叫參數（key-value）。
        description: 此測試案例的簡述。
    """

    input_id: str
    entry_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class TestInputSet(BaseModel):
    """一組測試輸入資料。"""

    inputs: list[TestInput] = Field(default_factory=list)


class GoldenRecord(BaseModel):
    """舊程式碼對某筆測試輸入的執行結果（標準答案）。

    Attributes:
        input_id: 對應 TestInput 的 input_id。
        entry_id: 對應 TestableEntry 的 entry_id。
        output: 捕獲的輸出（return value / stdout 序列化）。
        exit_code: 程式結束碼。
        stderr_snippet: stderr 片段。
        duration_ms: 執行時間（毫秒）。
    """

    input_id: str
    entry_id: str
    output: Any = None
    exit_code: int | None = None
    stderr_snippet: str | None = None
    duration_ms: int | None = None


class GoldenSnapshot(BaseModel):
    """所有 golden record 的集合。"""

    records: list[GoldenRecord] = Field(default_factory=list)


class ComparisonVerdict(str, Enum):
    """單筆測試比較的判定結果。"""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


class ComparisonResult(BaseModel):
    """新舊程式碼單筆輸出的比較結果。

    Attributes:
        input_id: 對應 TestInput 的 input_id。
        entry_id: 對應 TestableEntry 的 entry_id。
        verdict: 判定結果。
        expected_output: golden（舊）的輸出。
        actual_output: 重構後（新）的輸出。
        diff_summary: 差異摘要。
    """

    input_id: str
    entry_id: str
    verdict: ComparisonVerdict
    expected_output: Any = None
    actual_output: Any = None
    diff_summary: str | None = None


class EmittedTestFile(BaseModel):
    """產出的可執行測試原始碼檔案。

    Attributes:
        path: 測試檔案相對路徑。
        language: 目標語言（python、go、typescript 等）。
        content: 測試原始碼內容。
        entry_ids: 此檔案涵蓋的 entry_id 清單。
    """

    path: str
    language: str
    content: str
    entry_ids: list[str] = Field(default_factory=list)


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


class TestReport(BaseModel):
    """測試生成模組的最終報告。

    Attributes:
        run_id: 所屬 run 的識別碼。
        iteration: 迭代輪次（0 表示迭代前）。
        total: 測試案例總數。
        passed: 通過數。
        failed: 失敗數。
        errored: 錯誤數。
        skipped: 跳過數。
        pass_rate: 通過率（0.0 ~ 1.0）。
        coverage_pct: 行覆蓋率百分比。
        results: 每筆比較結果。
        emitted_files: 產出的測試檔案。
    """

    run_id: str
    iteration: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    coverage_pct: float | None = None
    results: list[ComparisonResult] = Field(default_factory=list)
    unit_test_results: list[UnitTestResult] = Field(default_factory=list)
    emitted_files: list[EmittedTestFile] = Field(default_factory=list)
