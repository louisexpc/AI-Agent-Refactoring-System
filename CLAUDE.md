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
- 策略：Golden Master / Snapshot Testing
- **迭代前**：`run_overall_test()` 建立整個 repo 的 golden baseline
- 以 file 級別為單位（沒function級別資料），LLM 讀整個檔案直接生成測試

#### `run_overall_test()` 內部流程（迭代前 + 迭代中都用）
```
Phase 1: File Filter — 從 DepGraph 過濾目標語言檔案 → list[SourceFile]
Phase 2: Guidance — LLM 逐檔分析（含依賴檔案 signatures context），每個檔案獨立產生一份測試指引（副作用、mock 建議等）
Phase 3: Golden Capture — 逐檔生成呼叫腳本（含依賴檔案 signatures context）→ coverage run 執行舊 code → 捕獲 golden output + coverage%
  - 按 source_files list 順序處理，每個腳本獨立執行（透過 sys.path.insert 解決同目錄依賴）
  - 沒有可執行行為的檔案（純 data class / constants）會嘗試 instantiate，失敗則記錄 exit_code!=0
Golden Comparison（僅迭代時）— 同樣腳本跑重構後 code → normalize → diff 新舊輸出
  - normalize = 清洗非確定性欄位（時間戳→<TIMESTAMP>、UUID→<UUID>、記憶體位址→<ADDR>），避免誤判 FAIL
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
├── source_files.json      # Phase 1: 過濾後的來源檔案
├── guidance.json           # Phase 2: 測試指引
├── golden_snapshot.json    # Phase 3: golden output
├── overall_report.json     # Overall test 報告
├── module_report_*.json    # Module test 報告
└── emitted/                # Phase 4: 可執行測試檔
    ├── test_sensor.py
    └── ...

artifacts/<run_id>/logs/test_gen/
├── golden/                    # Golden capture 的中間產物（debug 用）
│   ├── *_script.py            # LLM 生成的呼叫腳本
│   └── *.log                  # 腳本執行的 stdout/stderr
└── unit_test/                 # Module test 的 pytest 執行 log
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
- TODO: 考慮加入 golden capture 的 coverage（用 `coverage run` 執行腳本），作為測試充分性的參考指標
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
