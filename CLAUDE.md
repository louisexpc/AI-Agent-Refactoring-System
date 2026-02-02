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
## 整體 Pipeline 架構

### 迭代前 Pipeline
```
Repo Info → Initial Prompt → Analyze & Plan（Template Prompt）→ 產出 Plan
                                                                  ↓
                                              run_overall_test() 建立 golden baseline
                                                                  ↓
                                                        人工介入審核
                                                                  ↓
                                                      Start Prompt → 開始迭代
```

### 迭代 Pipeline（每個 Stage）
```
Stage Plan
  ↓
Clone last stage repo → 修改 Code
  ↓
Unit Test（Apply Agent 自行生成，呼叫 run_module_test()）
  ↓
Evaluation Unit Test ──Failed──→ Generate Report → 重回這次 Stage
  ↓ Success
是否為最後 Stage?
  ├─ 否 → run_overall_test(refactored_repo_dir=...)
  │         ├─ Failed → Generate Report → 重回 Stage
  │         └─ Success → Generate Report / Next Stage Plan / Commit
  └─ 是 → run_overall_test(refactored_repo_dir=最終版本)
            ├─ Failed → Generate Report
            └─ Success → Generate Final Report
```

### 模組分工
#### Repo Loader (Louis)
- Target: Clone All files + PR 報告 → Local Cache + Indexing Database
- 對外 API：接 `repo_url` + `prompt`(Optional)
- AST（依賴性分析）→ 產出 DepGraph

#### Analyze & Plan (Jesse, Karl)
- Target: Agent 分析整體 repo + 產出重構計畫（大 Plan → Stage 1, 2, 3...）
- 提供 Prompt Template 引導重構方向 + 人工調整 Prompt
- 分析 Module Dependency 決定修改順序

#### Generate Test (Yoyo)
- 策略：Golden Master / Snapshot Testing + Unit Test 雙層驗證
- **核心概念**：golden output 的值（如 `"Race_points_firstPlace": 25`）是語言無關的業務邏輯正確答案，可跨語言、跨結構使用
- `run_overall_test()`: 整體 golden snapshot（行為快照），不產生可執行 test file
  - 迭代前：逐檔建立 golden baseline（LLM 生成呼叫腳本 → 執行舊 code → 捕獲 stdout 作為標準答案）
  - 迭代時（介面未變）：同樣腳本跑新 code → normalize → diff
  - 迭代時（介面已變）：需搭配 behavior mapping，LLM 讀新 code + golden values → 生成新語言測試腳本 → 比對（尚未實作）
- `run_module_test()`: 針對單一 module 生成 + 執行 unit test（產生 pytest test file）
- 以 file 級別為單位（沒 function 級別資料），LLM 讀整個檔案 + 依賴檔案 signatures

#### Golden Comparison 的限制與跨結構方案

**問題**：重構後介面幾乎一定會變（class 改名、function 拆分、換語言），現有 Golden Comparison（同一份腳本跑新 code）會直接 ImportError / AttributeError 失敗。

**跨結構 Golden Comparison 方案（Behavior Mapping）**：
```
迭代前（已實作）：
  逐檔讀舊 code → LLM 生成呼叫腳本 → 執行 → 記錄 golden output
  golden output 的值是語言無關的業務正確答案
  例：A.py → {"Race_points_first": 25, "Leaderboard_rankings": [...]}

Apply Agent 重構（Apply 模組負責）：
  A.py → race.go + leaderboard.go
  Agent 同時輸出 behavior mapping（JSON 格式）：
  - 哪些 golden key 對應到哪些新檔案
  - 舊行為在新 code 裡的等價呼叫方式

驗證（Generate Test 消費 mapping）：
  LLM 讀新檔案原始碼 + 對應的 golden values
  → 生成新語言的測試腳本（Go test / Java test / pytest）
  → 執行新 code → 比對 golden values（機械式 JSON diff）

重點：
  - Golden values（25, [...], true）不分語言，是業務邏輯的真相
  - LLM 只負責「讀新 code → 生成能跑的測試」，不負責判斷對錯
  - 比較是機械式的（normalize + diff），不靠 LLM 判斷
  - 每個檔案都要跑（不只改過的），因為依賴可能有連鎖影響
```

**Behavior Mapping 介面（Apply Agent 需輸出，尚未定義 Pydantic model）**：
```json
{
  "old_file": "A.py",
  "new_files": ["race.go", "leaderboard.go"],
  "mappings": [
    {
      "golden_key": "Race_points_firstPlace",
      "golden_value": 25,
      "description": "First place in a race gets 25 points",
      "new_file": "race.go",
      "new_call_hint": "Race.Points(driver)"
    }
  ]
}
```
- `golden_key` + `golden_value`: 來自 golden_snapshot.json
- `new_file`: 該行為在重構後位於哪個檔案
- `new_call_hint`: 給 LLM 的提示，實際測試腳本由 LLM 讀新 code 原始碼後生成
- mapping 由 Apply Agent 負責產出，Generate Test 只消費

#### `run_overall_test()` 內部流程（迭代前 + 迭代中都用）
```
Phase 1: File Filter — 從 DepGraph 過濾目標語言檔案 → list[SourceFile]
Phase 2: Guidance — LLM 逐檔分析（含依賴檔案 signatures context），每個檔案獨立產生一份測試指引（副作用、mock 建議等）
Phase 3: Golden Capture — 逐檔生成呼叫腳本（含依賴檔案 signatures context）→ coverage run 執行舊 code → 捕獲 golden output + coverage%
  - 按 source_files list 順序處理，每個腳本獨立執行（透過 sys.path.insert 解決同目錄依賴）
  - 沒有可執行行為的檔案（純 data class / constants）會嘗試 instantiate，失敗則記錄 exit_code!=0
  - golden output 的 key 採描述性命名（ClassName_methodName_scenario），作為跨結構比對的錨點
Golden Comparison（僅迭代時，介面未變）— 同樣腳本跑重構後 code → normalize → diff 新舊輸出
  - normalize = 清洗非確定性欄位（時間戳→<TIMESTAMP>、UUID→<UUID>、記憶體位址→<ADDR>），避免誤判 FAIL
Golden Comparison（僅迭代時，介面已變，尚未實作）— 消費 behavior mapping → LLM 生成新語言測試 → 比對 golden values
Report — 彙總 golden comparison results → OverallTestReport
```

#### `run_module_test()` 內部流程(可能需要plan資訊，先不處理)
```
Phase 1: 讀取單一來源檔案 → SourceFile
Phase 2: Guidance — LLM 分析該檔案（含依賴檔案 signatures）
Phase 3: Golden Capture — coverage run 執行舊 code 建立 baseline + coverage%
Phase 4: Test Emitter — LLM 讀整個檔案 + guidance + golden output → 生成 test file
Phase 5: Test Runner — pytest 執行 → 收集 pass/fail + coverage
（若有 refactored_repo_dir）— 同一組 test 跑新 code → 比對 baseline
```

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
├── source_files.json      # run_overall_test: Phase 1 過濾後的來源檔案
├── guidance.json           # run_overall_test: Phase 2 測試指引
├── golden_snapshot.json    # run_overall_test: Phase 3 golden output（行為快照）
├── overall_report.json     # run_overall_test: 最終報告
├── module_report_*.json    # run_module_test: 單模組報告
└── emitted/                # run_module_test: Phase 4 產出的 pytest test file
    ├── test_sensor.py
    └── ...

artifacts/<run_id>/logs/test_gen/
├── golden/                    # run_overall_test: golden capture 中間產物
│   ├── *_script.py            # LLM 生成的「呼叫腳本」（非 test file）
│   ├── *.coverage             # coverage 資料檔
│   └── *.log                  # 腳本執行的 stdout/stderr
├── module_golden/             # run_module_test: 單模組的 golden capture
└── unit_test/                 # run_module_test: pytest 執行 log
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

**guidance.json** — LLM 分析每個檔案產出的測試指引
```json
{ "guidances": [
    { "module_path": "Python/Leaderboard/leaderboard.py",
      "side_effects": [],
      "mock_recommendations": [],
      "nondeterminism_notes": null,
      "external_deps": [] }
]}
```
- `nondeterminism_notes`: LLM 標註的非確定性行為（如 random、datetime.now()、環境變數），帶入 Phase 3 prompt 讓 LLM 知道要 mock 掉這些來源

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
- output 的 key 採描述性命名（`ClassName_methodName_scenario`），方便辨識測試內容

**overall_report.json** — `run_overall_test()` 的最終報告
```json
{ "run_id": "f3f7...",
  "golden_snapshot": { "records": [...] },
  "comparison_results": [],
  "pass_rate": 0.0 }
```
- `comparison_results` 迭代前為空，迭代時包含每個檔案的 PASS/FAIL/ERROR/SKIPPED
- `pass_rate` 迭代前為 0.0（無比較對象）
- golden capture 已使用 `coverage run` 執行腳本，coverage_pct 記錄在各 GoldenRecord 中

**module_report_*.json** — `run_module_test()` 的單模組報告(先不管)
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
### Criteria & Limitation（暫定）
- Can Build/Compile
- Coverage Ratio: 75%（Early Stopping Mechanism）
- Time Limit: 15 min per iteration
- Token Limit: 50K per iteration
- Maximum Iteration: 3

# Coding Style
- `ruff format`: 維護統一 coding style
- 註解 + 參數 `typing` 設定
    ```python
    def method(args: List, arg2: Dict)-> str:
        ```
        docstrings: Recommendation : Google Python Style Guide
        ```
    ```
