# TSMC 2026 Hackathon - AI 智能重構系統

AI 輔助的舊程式碼重構系統，支援跨語言轉換與自動化測試驗證。

## 問題描述

本專案解決三個重構場景：

| Project | 情境 | 評分標準 |
|---------|------|----------|
| **Project 1** | CLI 工具（12K+ 行），重構為同/異語言 | 邏輯正確性 70% + Coverage 30% |
| **Project 2** | MVC 後端渲染架構 → 前後端分離 | 後端重構 50% + 前端重構 50% |
| **Project 3** | 購物車系統，弱型別 → 強型別 + Raw SQL | Backend 70% + SQL Coverage 30% |

### 限制條件
- 只能輸入 init prompt 和 start prompt
- 輸入：Repo URL + Prompt
- 輸出：每輪迭代產出重構評估報告 + 下輪計畫
- 平台：GCP

---

## 系統架構

### 整體 Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        迭代前 Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  Repo URL                                                        │
│      ↓                                                           │
│  Repo Loader (clone + DepGraph + RepoIndex)                     │
│      ↓                                                           │
│  Initial Prompt → Analyze & Plan → 產出大 Plan (Stage 1,2,3...) │
│      ↓                                                           │
│  人工審核 → Start Prompt → 開始迭代                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    迭代 Pipeline (每個 Stage)                    │
├─────────────────────────────────────────────────────────────────┤
│  Stage Plan (含 Module Mapping)                                  │
│      ↓                                                           │
│  Apply Agent 重構 → 產出新 code                                  │
│      ↓                                                           │
│  Generate Test (per module mapping):                             │
│    1. Build/Compile 檢查                                         │
│    2. Characterization Test (舊code→golden→新code→比對)          │
│    3. Line Coverage 收集                                         │
│      ↓                                                           │
│  Evaluation ──Failed──→ Generate Report → 重試 Stage            │
│      ↓ Success                                                   │
│  Generate Report / Next Stage Plan / Commit                     │
└─────────────────────────────────────────────────────────────────┘
```
---

## Generate Test 模組

### 核心策略：Characterization Testing

**原理**：執行舊程式碼取得真實輸出（golden output），再驗證新程式碼產出相同的值。

```
舊程式碼 ──執行──→ Golden Output (如 25, {"Hamilton": 43})
                       ↓
新程式碼 ──測試──→ 比對 Golden Output → Pass/Fail
```

Golden output 是**語言無關的業務邏輯正確答案**，支援跨語言重構驗證。

### 處理單位：Module

一個 **module** 是 Stage Plan 中一組 before/after 檔案的對應。例如：

```json
{
  "before": ["Python/TirePressureMonitoringSystem/sensor.py",
             "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
  "after":  ["Python/TirePressureMonitoringSystem/sensor.py",
             "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"]
}
```

- 一個 module 可以包含 **1~N 個檔案**（多個彼此有 import 關係的檔案組成一個 module）
- 整個 module 的所有檔案會**聚合成一份原始碼**送給 LLM
- 每個 module 產出**一個 golden script** 和**一個 test file**
- 一個 Stage 可以有**多個 module mappings**，各自獨立測試

### 詳細處理流程

```
輸入：stage_mappings + dep_graph + repo_dir + refactored_repo_dir

  For each module mapping:
  ┌──────────────────────────────────────────────────────────────┐
  │ Phase 1: Guidance 生成                                       │
  │   DepGraph 提取依賴 → AST 擷取 signatures → LLM 分析        │
  │   產出：side_effects, mock_recommendations, nondeterminism   │
  ├──────────────────────────────────────────────────────────────┤
  │ Phase 2: Golden Capture（舊 code + 舊語言 plugin）          │
  │   聚合 before_files 原始碼                                    │
  │   + DepGraph 依賴的 signatures                                │
  │   + Guidance                                                  │
  │   → LLM 生成 golden script                                   │
  │   → coverage run 執行 → 收集 golden output (JSON)            │
  ├──────────────────────────────────────────────────────────────┤
  │ Phase 3: Test Emit（新 code + 新語言 plugin）                │
  │   聚合 after_files 原始碼                                     │
  │   + Golden output (keys + values)                             │
  │   + DepGraph 依賴的 signatures                                │
  │   + Guidance                                                  │
  │   → LLM 生成 pytest test file                                │
  ├──────────────────────────────────────────────────────────────┤
  │ Phase 4: Test Run                                             │
  │   設定 PYTHONPATH + conftest.py（source_dirs 優先）           │
  │   → pytest -v + coverage 執行                                │
  │   → 解析個別 test item 結果 + failure_reason                  │
  │   → 收集 coverage                                            │
  └──────────────────────────────────────────────────────────────┘

  最後：
  ┌──────────────────────────────────────────────────────────────┐
  │ Build Check                                                   │
  │   python -m compileall 檢查新 code 是否能編譯                 │
  ├──────────────────────────────────────────────────────────────┤
  │ Review 生成                                                   │
  │   LLM 比對新舊原始碼 + 測試結果                               │
  │   → semantic_diff + risk_warnings（per-module）              │
  │   → test_item_reviews（per-test-item）                       │
  ├──────────────────────────────────────────────────────────────┤
  │ 寫入 3 個 Artifact 檔案                                      │
  │   summary.json / test_records.json / review.json             │
  └──────────────────────────────────────────────────────────────┘
```

### DepGraph 的作用

DepGraph（依賴圖）記錄 repo 中所有檔案的 import 關係。Generate Test 在兩個地方使用它：

1. **Guidance 生成**：LLM 分析原始碼時，dep_graph 告訴它這個檔案 import 了哪些其他檔案，幫助識別 side effects 和 mock 建議
2. **Golden Capture / Test Emit**：LLM 生成腳本時，`dep_resolver.py` 根據 dep_graph edges 定位依賴檔案，用 AST 提取 **signatures** 後傳給 LLM，讓它了解依賴的 API 形狀

```
dep_graph.edges:  sensor.py → random (stdlib, 跳過)
                  tire_pressure_monitoring.py → sensor.py (internal)

解析後提供給 LLM:
  "--- sensor.py ---
   class Sensor:
       def pop_next_pressure_psi_value(self) -> float: ...
       @staticmethod
       def sample_pressure() -> float: ..."
```

注意：dep_graph 本身只提供依賴 **edges**（哪個檔案 import 哪個檔案）。`dep_resolver.py` 根據這些 edges 讀取依賴檔案，再用 AST 只提取 **signatures**（class/function 簽名，不含 body），避免 context 過長。

### Module Mapping 的作用

Module Mapping 定義「舊 code 的哪些檔案對應到新 code 的哪些檔案」：

- **一對一**：`sensor.py` → `sensor.py`（同檔名重構）
- **一對多**：`leaderboard.py` → `leaderboard.py` + `driver.py`（拆分）
- **多對一**：`utils.py` + `helpers.py` → `common.py`（合併）
- **多對多**：整個子目錄重構

Golden Capture 使用 `before_files`，Test Emit 和 Test Run 使用 `after_files`。兩邊的 golden output keys 透過 LLM 語意對應。

### 錯誤處理

| 階段 | 錯誤類型 | 處理方式 |
|------|----------|----------|
| Guidance 生成 | LLM JSON 解析失敗 | 回傳空 guidance，pipeline 繼續 |
| Golden Capture | LLM 生成的腳本執行失敗 | 記錄 exit_code 和 stderr，golden_output 為 null |
| Golden Capture | LLM 回應非 JSON | 嘗試 `json.loads(last_line)`，再嘗試整段，最後存原始文字 |
| Test Emit | LLM 包含 markdown fences | 自動 strip ```` ```python ```` 和 ```` ``` ```` |
| Test Run | import 找不到 module | conftest.py 注入 source_dirs 到 sys.path 最前面 |
| Test Run | 使用 mocker fixture | prompt 明確禁止 pytest-mock，要求用 unittest.mock |
| Test Run | pytest setup error | 從 ERRORS section 解析 failure_reason |
| Test Run | 超時 | 回傳 exit_code=-1, stderr="TIMEOUT" |
| Review 生成 | LLM JSON 解析失敗 | semantic_diff 填 "[LLM parse failure]"，pipeline 繼續 |
| Build Check | 編譯失敗 | build_success=false，build_error 記錄訊息 |

### conftest.py 的作用

`conftest.py` 是 pytest 的特殊配置檔，在 `run_tests()` 時自動生成。它把 source module 的目錄插入 `sys.path` 的**最前面**。

原因：Python 的 `sys.path[0]` 預設是 `''`（即 cwd = repo root），優先順序比 PYTHONPATH 還高。如果 repo root 有同名檔案，Python 會找到錯的 module。conftest.py 在所有 test import 之前執行 `sys.path[:0] = [...]`，確保正確的 module 被優先找到。

```python
# 自動生成的 conftest.py 範例
import sys
sys.path[:0] = ['/path/to/repo/Python/TirePressureMonitoringSystem']
```

### 輸入格式

#### Module Mapping JSON (`mock_mapping.json`)

```json
{
  "source_language": "python",
  "target_language": "python",
  "repo_dir": "artifacts/<run_id>/snapshot/repo",
  "refactored_repo_dir": "artifacts/<run_id>/snapshot/repo",
  "dep_graph_path": "artifacts/<run_id>/depgraph/dep_graph.json",
  "mappings": [
    {
      "before": ["Python/TirePressureMonitoringSystem/sensor.py",
                 "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
      "after": ["Python/TirePressureMonitoringSystem/sensor.py",
                "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"]
    }
  ]
}
```

| 欄位 | 說明 |
|------|------|
| `source_language` | 舊程式碼語言 (python/go/java) |
| `target_language` | 新程式碼語言 |
| `repo_dir` | 舊程式碼 repo 路徑 |
| `refactored_repo_dir` | 重構後 repo 路徑 |
| `dep_graph_path` | 依賴圖 JSON 路徑 |
| `mappings` | Module 對應清單（每組是一個 module） |
| `mappings[].before` | 舊 repo 的檔案路徑（可以多個） |
| `mappings[].after` | 新 repo 的檔案路徑（可以多個） |

#### DepGraph JSON 格式

```json
{
  "nodes": [
    {
      "path": "Python/TirePressureMonitoringSystem/sensor.py",
      "lang": "python",
      "ext": ".py"
    }
  ],
  "edges": [
    {
      "src": "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py",
      "dst": "Python/TirePressureMonitoringSystem/sensor.py",
      "kind": "import"
    }
  ]
}
```

DepGraph 由 Repo Loader 模組生成。Generate Test 只讀取它，用於：
- 查找每個檔案的依賴（`edges` 中 `src` 為該檔案的所有 `dst`）
- 提取依賴檔案的 signatures（AST class/function 簽名）

### 輸出格式

#### Artifact 目錄結構

```
artifacts/<run_id>/
├── summary.json              # 統計數據 + build 狀態
├── test_records.json         # 事實：golden output + 每個 test item 狀態 + failure_reason
├── review.json               # LLM 分析：semantic diff + risk warnings + per-test-item 點評
├── golden/                   # Golden capture 產物
│   ├── *_script.py           # LLM 生成的呼叫腳本
│   ├── *.coverage            # Coverage 資料
│   └── *.log                 # 執行日誌
└── tests/                    # 生成的測試檔案
    ├── conftest.py           # 自動生成的 sys.path 注入
    ├── test_*.py             # Pytest 測試檔
    └── *.log                 # 測試執行日誌
```

三個 JSON 各自職責分明：

| 檔案 | 職責 | 消費者 |
|------|------|--------|
| `summary.json` | 統計數據，快速判斷 pass/fail | 上游 agent 的 if/else |
| `test_records.json` | 純事實：測了什麼、結果、failure_reason | debug / 追溯 |
| `review.json` | LLM 語意分析 + per-test-item 點評 + 風險評估 | 做決策的 agent 或人 |

#### summary.json — 統計

```json
{
  "run_id": "test_result",
  "build_success": true,
  "build_error": null,
  "overall_pass_rate": 1.0,
  "overall_coverage_pct": 80.0,
  "total_modules": 1,
  "total_passed": 9,
  "total_failed": 0,
  "total_errored": 0
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `run_id` | string | 本次執行的唯一識別碼 |
| `build_success` | bool | 新程式碼是否能成功編譯（`python -m compileall`） |
| `build_error` | string\|null | 編譯失敗時的錯誤訊息（成功時為 null） |
| `overall_pass_rate` | float | 所有測試的通過率 (0.0~1.0) |
| `overall_coverage_pct` | float | 所有 module 的平均行覆蓋率 |
| `total_modules` | int | 測試的 module 數量（= mappings 數量） |
| `total_passed` | int | 通過的測試總數 |
| `total_failed` | int | 失敗的測試總數（assertion 失敗） |
| `total_errored` | int | 錯誤的測試總數（setup/teardown error、import error 等） |

#### test_records.json — 事實

每個 module 測了什麼、golden output 是什麼、每個 test function 的結果和 failure_reason。

```json
{
  "run_id": "test_result",
  "modules": [
    {
      "before_files": ["Python/TirePressureMonitoringSystem/sensor.py",
                       "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
      "after_files": ["Python/TirePressureMonitoringSystem/sensor.py",
                      "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
      "golden_output": {
        "Sensor_sample_pressure_representative_call": 0.0959,
        "Alarm_is_alarm_on_initial_state": false,
        "Alarm_check_is_alarm_on_with_low_pressure": true
      },
      "golden_exit_code": 0,
      "golden_coverage_pct": 100.0,
      "tested_functions": ["Sensor_sample_pressure_representative_call", "..."],
      "test_file_path": "tests/test_sensor.py",
      "golden_script_path": "golden/Python_TirePressureMonitoringSystem_sensor_py_module_script.py",
      "test_items": [
        {"test_name": "test_sensor_sample_pressure", "status": "passed", "failure_reason": null},
        {"test_name": "test_alarm_check_low", "status": "failed", "failure_reason": "AttributeError: Mock..."}
      ],
      "aggregate_passed": 8,
      "aggregate_failed": 1,
      "aggregate_errored": 0,
      "coverage_pct": 80.0,
      "test_exit_code": 1
    }
  ]
}
```

##### modules[i] 欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `before_files` | array | 舊 repo 的檔案路徑（產生 golden output） |
| `after_files` | array | 新 repo 的檔案路徑（被測試的對象） |
| `golden_output` | object | Golden output：key 是測試項目描述，value 是舊程式碼的結果 |
| `golden_exit_code` | int | Golden capture 腳本的結束碼（0=成功） |
| `golden_coverage_pct` | float | Golden capture 的行覆蓋率 |
| `tested_functions` | array | Golden output 的 keys 清單（代表測了哪些功能） |
| `test_file_path` | string | 生成的測試檔相對路徑 |
| `golden_script_path` | string | Golden capture 腳本相對路徑 |
| `test_items` | array | 個別 test function 的結果（從 pytest -v 解析） |
| `test_items[].test_name` | string | 測試函式名稱 |
| `test_items[].status` | string | passed / failed / error / skipped |
| `test_items[].failure_reason` | string\|null | 失敗時的錯誤訊息（passed 時為 null） |
| `aggregate_passed` | int | 通過數 |
| `aggregate_failed` | int | 失敗數 |
| `aggregate_errored` | int | 錯誤數 |
| `coverage_pct` | float | 測試覆蓋率 |
| `test_exit_code` | int | pytest 結束碼 |

#### review.json — LLM 分析

LLM 比對新舊程式碼 + 測試結果，產出兩個層級的分析：
- **Module 層級**：`semantic_diff`（行為差異）、`risk_warnings`（風險清單）
- **Test Item 層級**：每個 test function 的 `test_purpose`、`result_analysis`、`failures_ignorable`

```json
{
  "run_id": "test_result",
  "modules": [
    {
      "before_files": ["Python/TirePressureMonitoringSystem/sensor.py",
                       "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
      "after_files": ["Python/TirePressureMonitoringSystem/sensor.py",
                      "Python/TirePressureMonitoringSystem/tire_pressure_monitoring.py"],
      "semantic_diff": "The new code is identical to the old code.",
      "risk_warnings": [
        {
          "description": "The Alarm class has a hard-coded dependency on Sensor",
          "severity": "medium",
          "tested_by_golden": false
        }
      ],
      "test_item_reviews": [
        {
          "test_name": "test_alarm_is_alarm_on_initial_state",
          "test_purpose": "Checks that a new Alarm has is_alarm_on initialized to False",
          "result_analysis": "Passed. The Alarm.__init__ is unchanged.",
          "failures_ignorable": false,
          "ignorable_reason": null
        },
        {
          "test_name": "test_alarm_check_scenarios[16.9-low_pressure]",
          "test_purpose": "Verifies alarm triggers for pressure below threshold",
          "result_analysis": "Failed due to mock setup error, not a real regression.",
          "failures_ignorable": true,
          "ignorable_reason": "Mock setup error, not a business logic issue"
        }
      ]
    }
  ],
  "overall_assessment": "Reviewed 1 module(s). No high-severity risks detected."
}
```

##### Module 層級欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `semantic_diff` | string | 新舊 code 的行為差異分析 |
| `risk_warnings` | array | 風險清單 |
| `risk_warnings[].description` | string | 風險描述 |
| `risk_warnings[].severity` | string | low / medium / high / critical |
| `risk_warnings[].tested_by_golden` | bool | 此風險是否已被 golden test 覆蓋 |

##### Test Item 層級欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `test_item_reviews` | array | 每個 test function 的 LLM 點評 |
| `test_item_reviews[].test_name` | string | 測試函式名稱 |
| `test_item_reviews[].test_purpose` | string | 該測試驗證什麼 |
| `test_item_reviews[].result_analysis` | string | 通過/失敗原因分析 |
| `test_item_reviews[].failures_ignorable` | bool | 失敗是否可忽略（預判性，不是當前狀態） |
| `test_item_reviews[].ignorable_reason` | string\|null | 可忽略的原因（`failures_ignorable=false` 時為 null） |

##### 三個檔案的關係

```
summary.json          test_records.json         review.json
─────────────         ─────────────────         ───────────
pass_rate: 100%       每個 test item 的          semantic_diff (per-module)
coverage: 80%         golden output + 狀態        risk_warnings (per-module)
                      + failure_reason             test_item_reviews (per-item)

  ↓ 快速判斷             ↓ 需要細節時看              ↓ 做最終決策
  pass / fail            debug / 追溯              是否接受重構
```

#### Golden Output 格式說明

Golden output 的 key 是 LLM 決定的描述性命名，代表「測試什麼 + 預期值」：

```json
{
  "Sensor_sample_pressure_representative_call": 0.0959,
  "Sensor_pop_next_pressure_psi_value_with_mocked_sample": 20.5,
  "Alarm_is_alarm_on_initial_state": false,
  "Alarm_check_is_alarm_on_with_low_pressure": true,
  "Alarm_stateful_check_remains_on_after_subsequent_normal_pressure": true
}
```

| Key 格式 | 含意 |
|----------|------|
| `ClassName_methodName_scenario` | 類別方法測試 |
| `functionName_scenario` | 函式測試 |

### Golden Output 生成與使用流程

```
┌──────────────────────────────────────────────────────────────┐
│ Phase 2: Golden Capture（只跑一次，舊 code）                  │
│                                                               │
│ 聚合 module 全部 before_files 原始碼                          │
│ + dep_graph 依賴的 signatures                                 │
│ + guidance (side effects, mock recommendations)               │
│ → LLM 生成 golden script                                     │
│ → coverage run 執行 → JSON stdout                            │
│                                                               │
│ 輸出: {"Sensor_sample_pressure": 0.09, "Alarm_initial": false}│
└──────────────────────────────────────────────────────────────┘
                              ↓
                     keys + values 傳遞
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 3: Test Emit（新 code）                                 │
│                                                               │
│ 聚合 module 全部 after_files 原始碼                           │
│ + golden output (keys + values)                               │
│ + dep_graph 依賴的 signatures                                 │
│ + guidance                                                    │
│ → LLM 生成 pytest test file                                  │
│ → 根據 key 的語意找新 code 中對應的功能                       │
│ → assert 新功能的輸出 == golden value                         │
└──────────────────────────────────────────────────────────────┘
```

**重點**：Key 只在 Golden Capture 生成一次，Test Emit **讀取**這些 keys 來對應新 code。

---

### TODO: 已知限制與優化方向

#### 已知限制

| 情境 | 問題 | 影響 |
|------|------|------|
| **Class 拆分/合併** | 舊 `Race.points()` → 新 `PointsCalculator.calc()` | Key 名稱不匹配，靠 LLM 語意對應 |
| **API 結構大改** | 舊有 5 個測試項，新只能對應 3 個 | 部分測試被跳過 |
| **新增功能** | 新 code 有舊 code 沒有的功能 | 新功能沒被 golden 覆蓋 |
| **跨語言命名差異** | Python `snake_case` vs Go `PascalCase` | Key 對應困難 |

#### 未來改進項目

- [ ] 儲存 Guidance 到檔案供 debug
- [ ] 報告中標示「無法對應的 golden keys」
- [ ] 支援 key mapping 設定檔（手動指定對應關係）
- [ ] 用 AST 提取 function signature 輔助對應

---

### API 使用

```python
from runner.test_gen import run_stage_test
from runner.test_gen.llm_adapter import create_vertex_client
from shared.test_types import ModuleMapping

# 建立 LLM client
llm_client = create_vertex_client()

# 執行 Stage 測試（外部唯一入口）
report = run_stage_test(
    run_id="test_001",
    repo_dir=repo_dir,
    refactored_repo_dir=refactored_repo_dir,
    stage_mappings=[ModuleMapping(before_files=[...], after_files=[...])],
    dep_graph=dep_graph,
    llm_client=llm_client,
    artifacts_root=Path("artifacts"),
    source_language="python",
    target_language="python",
)

# 產出：artifacts/test_001/summary.json, test_records.json, review.json
```

### Language Plugin 架構

語言相關操作抽象為插件：

| Plugin | Golden Script 執行 | Test 執行 | Coverage 工具 | Build 檢查 |
|--------|-------------------|-----------|--------------|------------|
| `PythonPlugin` | `coverage run script.py` | `pytest -v + coverage` | coverage.py | `compileall` |
| `GoPlugin` | stub | stub | go tool cover | stub |
| `JavaPlugin` | stub | stub | JaCoCo | stub |

PythonPlugin 的 PYTHONPATH 注入順序：
1. `source_dirs`（module 檔案的 parent 目錄，最高優先）
2. `work_dir/Python`（語言目錄）
3. `work_dir`（repo root）
4. 既有 `PYTHONPATH`

### 驗證標準

| 指標 | 說明 |
|------|------|
| **Build Success** | 新程式碼能否成功編譯 |
| **Pass Rate** | Characterization test 通過率 |
| **Coverage** | 新程式碼被測試覆蓋的行數比例 |

### 執行測試

```bash
# 執行 e2e 測試
uv run python -m scripts.test_e2e_characterization
```

---

## 開發環境設置

### 系統需求
- Python 3.12
- Node.js v22
- uv 0.9.27+

### Quick Start

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 建立環境
uv sync

# 啟用 pre-commit
uv run pre-commit install

# 安裝額外依賴 (for test_gen)
uv add google-auth google-cloud-aiplatform vertexai coverage pytest pytest-cov
```

### 套件管理

```bash
# 執行 Python
uv run python <your_script.py>

# 安裝套件
uv add <package>
```

---

## 協作規範

### GitHub 規範
- 禁止 direct push 到 main
- Require PR reviews (至少 1-2 人 + Copilot)
- Require status checks to pass
- Block force pushes / deletion

### Branch 命名
```
<type>/<ticket>-<short-slug>
```
- type: `feat|fix|chore|docs|refactor|test|infra|ci`

### Coding Style
- `ruff format` 統一格式
- Type hints + Google style docstrings

```python
def method(args: list, arg2: dict) -> str:
    """Brief description.

    Args:
        args: Description.
        arg2: Description.

    Returns:
        Description.
    """
```

---

## 專案結構

```
repo-root/
├── api/                    # FastAPI service
├── orchestrator/           # LangGraph workflow
├── runner/                 # Cloud Run Job + adapters
│   └── test_gen/           # Generate Test 模組
│       ├── plugins/        # Language plugins (Python/Go/Java)
│       ├── main.py         # Orchestrator（公開 API）
│       ├── golden_capture.py  # Golden output 捕獲
│       ├── test_emitter.py    # LLM 生成 test file
│       ├── test_runner.py     # 執行 test + 解析結果
│       ├── guidance_gen.py    # LLM 生成測試指引
│       ├── review_gen.py      # LLM semantic diff + 風險評估
│       ├── dep_resolver.py    # DepGraph 依賴 signatures 提取
│       ├── llm_adapter.py     # Vertex AI Gemini adapter
│       └── report_builder.py  # 建立 summary / test_records
├── eval/                   # Metrics, scoring
├── web/                    # React frontend
├── shared/                 # Shared schemas (test_types.py, ingestion_types.py)
├── scripts/                # Dev scripts (test_e2e_characterization.py)
├── artifacts/              # 測試產物
└── docs/                   # 文件
```

---

## 評分標準（暫定）

| 標準 | 閾值 |
|------|------|
| Build/Compile | 必須通過 |
| Coverage Ratio | ≥ 75% (Early Stopping) |
| Time Limit | 15 min/iteration |
| Token Limit | 50K/iteration |
| Max Iterations | 3 |
