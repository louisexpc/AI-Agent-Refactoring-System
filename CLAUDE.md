# 題目 : AI 舊程式碼智能重構，可量化AI輔助系統，實現迭代翻新
##  三個要解決的Project
Project1:熱門語言寫出來的CLI工具，代碼規模12K+，要refactor成某語言(也可能是本身)
  主要測試邏輯正確性和Test Coverage
  邏輯正確性(70%)
  Test Coverage(30%)

Project2:MVC架構，由後端渲染HTML，為早年流行的架構，現在該語言開發者少，但專案仍具有價值，期望以現代語言重構成前後端分離的架構
  主要測試Agent對於非主流語言的轉換能力，以及是否可以將UI從後端邏輯集裡面撥離出
  後端重構成其他語言(50%)
  前端重構成其他語言(50%)

Project3:經典購物車系統，由熱門語言撰寫
  主要測試弱型別語言轉強型別語言Agent要可以理解不同類席資料庫的差異，並妥善轉成RAW SQL
  Backend重構成強型別(70%)
  所有的RAW SQL都要可以被測試覆蓋(30%)

- 只可以輸入init prompt和start prompt
- 輸入 : repo網址&prompt
- 輸出 : 每輪迭代需產出重構評估報告、下輪計畫
- UI不限格式，可以是CLI、Web等等
- 平台 : GCP
## 迭代前 Pipeline
### Repo Loader (Louis)
- Target: Clone All files + PR 報告 -> Local Cache + Indexing Database(or method)
- 對外 API : 接 `repo_url` + `prompt`(Optional)
- AST (依賴性分析)
### Analyze & Plan (Jesse, Karl)
- Target: Agent 分析整體 repo + 重構計畫
- 提供一個 Prompt Template 引導重構方向 + 人工調整 Prompt
Recommendations:
- 分析 Module Dependency 決定改訂計畫 + Test Cases 測試
### Generate Test (Yoyo)
- 策略：Golden Master / Snapshot Testing + Unit Test 雙層驗證
- 對外 API：兩個入口，供迭代 pipeline 呼叫
  - `run_overall_test()`: 建立 golden baseline / 執行 golden comparison
  - `run_module_test()`: 針對單一 module 生成 + 執行 unit test
- 所有 LLM 依賴的模組在 `llm_client=None` 時都有 stub fallback
- 以 file 級別為單位（非 function 級別），LLM 讀整個檔案直接生成測試

#### Pipeline 呼叫流程
```
階段一（迭代前）：
  run_overall_test(refactored_repo_dir=None)
  → File Filter → Guidance → Golden Capture → 建立 baseline

階段二（每個 Stage）：
  ① run_module_test(file_path="moduleA.py")
     → 讀舊 code → LLM 生成 unit test → 跑舊 code baseline
  ② Apply Agent 重構 moduleA
  ③ run_module_test(file_path="moduleA.py", refactored_repo_dir=...)
     → 同一組 test 跑新 code → 比對 baseline
  ④ run_overall_test(refactored_repo_dir=...)
     → golden comparison 確認整體行為不變
  → 兩種都 pass → 進入下一個 Stage

最終驗收：
  run_overall_test(refactored_repo_dir=最終版本)
  → 產出 Final Report
```

#### Phase 說明
**Phase 1：File Filter**
- 從 DepGraph 過濾目標語言檔案（.py/.go/.js/.ts）
- 讀取檔案內容，產出 `list[SourceFile]`

**Phase 2：LLM 生成測試指引（Guidance）**
- LLM 讀整個檔案原始碼，產出結構化 JSON 指引
- 內容：副作用識別、mock 建議、非確定性行為、外部依賴

**Phase 3：Golden Capture（file 級別）**
- LLM 生成每個檔案的呼叫腳本（呼叫所有 public function）
- subprocess 執行舊 code，捕獲 stdout 作為 golden output

**Phase 4：Test Code Emitter**
- LLM 讀整個檔案 + guidance + golden output → 直接生成完整 test file
- LLM 自行決定測哪些函式、用什麼 input、assert 什麼

**Phase 5：Test Runner**
- subprocess 跑 pytest 執行 emitted 測試檔案
- 收集 pass/fail 數量 + pytest-cov coverage 百分比

**Golden Comparison（迭代時才執行）**
- 用同樣腳本跑重構後 code，normalize 後 diff 新舊輸出
- OutputNormalizer 清洗時間戳、UUID 等非確定性欄位

**Report Builder**
- 彙總 golden comparison results → OverallTestReport

#### 對外 API
```python
from runner.test_gen import run_overall_test, run_module_test

# API 1: 整體 golden test
overall_report = run_overall_test(
    run_id="abc123",
    repo_dir=Path("path/to/legacy/code"),
    dep_graph=dep_graph,              # DepGraph
    repo_index=repo_index,            # RepoIndex
    llm_client=llm_client,            # VertexLLMClient 或 None
    artifacts_root=Path("artifacts"),
    target_language="python",
    refactored_repo_dir=None,         # 迭代時傳入
)
# overall_report.golden_snapshot, .comparison_results, .pass_rate

# API 2: 單一 module unit test
module_report = run_module_test(
    run_id="abc123",
    repo_dir=Path("path/to/legacy/code"),
    file_path="src/moduleA.py",       # 從 Stage Plan 拿到
    llm_client=llm_client,
    artifacts_root=Path("artifacts"),
    target_language="python",
    refactored_repo_dir=None,         # 重構後傳入
)
# module_report.can_test, .emitted_file, .baseline_result,
# .refactored_result, .coverage_pct
```

#### Artifact 輸出
```
artifacts/<run_id>/test_gen/
├── source_files.json      # Phase 1: 過濾後的來源檔案
├── guidance.json           # Phase 2: 測試指引
├── golden_snapshot.json    # Phase 3: golden output
├── overall_report.json     # Overall test 報告
├── module_report_*.json    # Module test 報告
└── emitted/                # Phase 4: 可執行測試檔
    ├── test_sensor.py
    └── ...
```

#### Artifact JSON 格式說明

**source_files.json** — 從 DepGraph 過濾出的目標語言檔案（只存路徑，不存內容）
```json
{ "files": [
    { "path": "Python/Leaderboard/leaderboard.py",
      "lang": "python" }
]}
```
- 檔案內容透過 `SourceFile.read_content(repo_dir)` 按需從磁碟讀取

**guidance.json** — LLM 分析每個檔案產出的測試指引（stub mode 時為空值）
```json
{ "guidances": [
    { "module_path": "Python/Leaderboard/leaderboard.py",
      "side_effects": [],
      "mock_recommendations": [],
      "nondeterminism_notes": null,
      "external_deps": [] }
]}
```

**golden_snapshot.json** — 執行舊 code 的 golden baseline 輸出
```json
{ "records": [
    { "file_path": "Python/Leaderboard/leaderboard.py",
      "output": { ... },
      "exit_code": 0,
      "stderr_snippet": null,
      "duration_ms": 120 }
]}
```
- `exit_code=0` 正常，`1` 表示腳本執行失敗，`-1` 表示 timeout 或例外
- `output` 為 JSON 物件（成功時）或 null（失敗時）

**overall_report.json** — `run_overall_test()` 的最終報告
```json
{ "run_id": "f3f7...",
  "golden_snapshot": { "records": [...] },
  "comparison_results": [],
  "pass_rate": 0.0 }
```
- `comparison_results` 迭代前為空，迭代時包含每個檔案的 PASS/FAIL/ERROR/SKIPPED
- `pass_rate` 迭代前為 0.0（無比較對象）

**module_report_*.json** — `run_module_test()` 的單模組報告
```json
{ "run_id": "f3f7...",
  "file_path": "Python/.../sensor.py",
  "can_test": true,
  "emitted_file": { "path": "test_sensor.py", "language": "python", "content": "..." },
  "baseline_result": { "total": 3, "passed": 2, "failed": 1, "coverage_pct": 80.0 },
  "refactored_result": null,
  "coverage_pct": null }
```
- `can_test=false` 時其餘欄位皆為 null
- `refactored_result` 只在傳入 `refactored_repo_dir` 時才有值
## 迭代 Pipeline(尚未實作)
- Package : LanGraph
Iterative Loop：Analyze → Plan → Apply → Validate → Report → Decide → 下一輪/停止
---
### Analyze & Plan
- Input: 上輪 report + Init Plan，
- Output: 本輪 tasks（分優先序與風險）
- Metrics
    - 每輪計畫可執行率（plan→apply 成功比例）
    - 任務粒度（每輪平均改動檔案數/LOC）
---
### Apply(修改Code)
- Tool: Git/OS/Coding Style Tool/DB API
- Input: Task from `Analyze & Plan`
- Output: Commit on Repo + Reports
---
### Validate
- Unit Test + General Test
- Metrics:
    - Line Coverage
- Output: Test Report + Validation Score
### Fallback(暫定要加)
- 觸發: Test Case 通過率低於上一輪(暫定) or Line Coverage 降低
---
### Report
- 產出本輪報告 + 下輪 Start Prompt
### Criteria & Limitation(暫定)
- Can Build/Compile
- Coverage Ratio: 75%
    - Early Stopping Mechnism
- Time Limit: 15 min per iteration
- Token Limit: 50 K per interation
- Maximun Iteration : 3

# Coding Style
- `ruff format`: 維護統一 coding style
- 註解 + 參數 `typing` 設定
    ```python
    def method(args: List, arg2: Dict)-> str:
        ```
        docstrings: Recommendation : Google Python Style Guide
        ```
    ```
#   問題&想法(還不實作)
- 記憶庫機制 (Refactor Memory)
為解決 LLM 在長流程中的遺忘問題，維護一個輕量級 RAGJSON 檔：
**內容**：Key 為 Python 原始函式名，Value 為重構後的 Go 函式簽名。
**用途**：當重構上層業務邏輯 (Level N) 時，直接查表獲取底層 (Level N-1) 的正確呼叫方式，避免參數不匹配。
- 循環依賴處理 (Dependency Inversion)
- 視覺化演示設計 (For Demo)
- 在儀表板中實作互動式圖表：
**動態節點**：正在重構的檔案節點會閃爍或高亮顯示。
**顏色編碼**：灰色 (Pending) -> 黃色 (Processing) -> 紅色 (Error) -> 綠色 (Done)。
**目的**：讓評審直觀理解運作過程。
- Lrgacy code如果根本跑不起來?要怎麼驗證?
#   實作更新
模組實作：

- `runner/test_gen/__init__.py` — 匯出 `run_overall_test`, `run_module_test`
- `runner/test_gen/main.py` — Orchestrator，提供兩個 API
- `runner/test_gen/file_filter.py` — Phase 1: 從 DepGraph 過濾目標語言檔案
- `runner/test_gen/guidance_gen.py` — Phase 2: LLM 生成測試指引
- `runner/test_gen/golden_capture.py` — Phase 3: LLM 生成呼叫腳本 + subprocess 捕獲 golden output（file 級別）
- `runner/test_gen/test_emitter.py` — Phase 4: LLM 讀整個檔案生成完整 test file
- `runner/test_gen/test_runner.py` — Phase 5: subprocess 跑 pytest 收集 pass/fail + coverage
- `runner/test_gen/golden_comparator.py` — Golden Comparison: normalize 後 diff 新舊輸出
- `runner/test_gen/output_normalizer.py` — 清洗時間戳/UUID 等非確定性欄位
- `runner/test_gen/report_builder.py` — 彙總報告
- `runner/test_gen/llm_adapter.py` — Vertex AI Gemini LLM client
- `shared/test_types.py` — 所有測試相關 Pydantic models（SourceFile, GoldenRecord, OverallTestReport, ModuleTestReport 等）
- `scripts/smoke_test_gen.py` — 開發用 smoke test（正式串接後不需要）
