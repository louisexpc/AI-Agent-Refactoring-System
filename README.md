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

### 測試流程

```
輸入：before_files + after_files + DepGraph

Step 1: Guidance 生成
  └→ LLM 分析原始碼，識別 side effects、mock 建議

Step 2: Golden Capture（舊程式碼）
  └→ LLM 生成呼叫腳本
  └→ 執行腳本 + 收集 coverage
  └→ 記錄 golden output (JSON 格式)

Step 3: Test Emit（新程式碼）
  └→ LLM 讀取新程式碼 + golden values
  └→ 生成目標語言的 pytest/test file

Step 4: Test Run
  └→ 執行 test file + 收集 coverage
  └→ assert 通過 = 行為等價
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
      "before": ["Python/Leaderboard/leaderboard.py"],
      "after": ["Python/Leaderboard/leaderboard.py"]
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
| `mappings` | Module 對應清單 |
| `mappings[].before` | 舊 repo 的檔案路徑 |
| `mappings[].after` | 新 repo 的檔案路徑 |

#### DepGraph JSON 格式

```json
{
  "nodes": [
    {
      "path": "Python/Leaderboard/leaderboard.py",
      "lang": "python",
      "ext": ".py"
    }
  ],
  "edges": [
    {
      "src": "Python/Leaderboard/leaderboard.py",
      "dst": "Python/Leaderboard/driver.py",
      "kind": "import"
    }
  ]
}
```

### 輸出格式

#### Artifact 目錄結構

```
artifacts/<run_id>/
├── summary.json              # 統計數據 + build 狀態
├── test_records.json         # 事實：golden output + 每個 test item 狀態
├── review.json               # LLM 分析：semantic diff + 風險評估
├── golden/                   # Golden capture 產物
│   ├── *_script.py           # LLM 生成的呼叫腳本
│   ├── *.coverage            # Coverage 資料
│   └── *.log                 # 執行日誌
└── tests/                    # 生成的測試檔案
    ├── test_*.py             # Pytest 測試檔
    └── *.log                 # 測試執行日誌
```

三個 JSON 各自職責分明：

| 檔案 | 職責 | 消費者 |
|------|------|--------|
| `summary.json` | 統計數據，快速判斷 pass/fail | 上游 agent 的 if/else |
| `test_records.json` | 純事實：測了什麼、輸入輸出 | debug / 追溯 |
| `review.json` | LLM 語意分析 + 風險評估 | 做決策的 agent 或人 |

#### summary.json — 統計

```json
{
  "run_id": "test_result",
  "build_success": true,
  "build_error": null,
  "overall_pass_rate": 1.0,
  "overall_coverage_pct": 86.05,
  "total_modules": 1,
  "total_passed": 6,
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
| `total_modules` | int | 測試的 module 數量 |
| `total_passed` | int | 通過的測試總數 |
| `total_failed` | int | 失敗的測試總數 |
| `total_errored` | int | 錯誤的測試總數 |

#### test_records.json — 事實

每個 module 測了什麼、golden output 是什麼、每個 test function 的結果。不含測試程式碼內容（那在 `tests/` 目錄）。

```json
{
  "run_id": "test_result",
  "modules": [
    {
      "before_files": ["Python/Leaderboard/leaderboard.py"],
      "after_files": ["Python/Leaderboard/leaderboard.py"],
      "golden_output": {
        "Race_points_first_place": 25,
        "Leaderboard_driver_rankings": ["Max", "Charles"]
      },
      "golden_exit_code": 0,
      "golden_coverage_pct": 100.0,
      "tested_functions": ["Race_points_first_place", "Leaderboard_driver_rankings"],
      "test_file_path": "tests/test_leaderboard.py",
      "golden_script_path": "golden/Python_Leaderboard_leaderboard_py_script.py",
      "test_items": [
        {"test_name": "test_race_points", "status": "passed"},
        {"test_name": "test_driver_instantiation", "status": "passed"},
        {"test_name": "test_leaderboard_rankings", "status": "failed"}
      ],
      "aggregate_passed": 2,
      "aggregate_failed": 1,
      "aggregate_errored": 0,
      "coverage_pct": 86.05,
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
| `aggregate_passed` | int | 通過數 |
| `aggregate_failed` | int | 失敗數 |
| `aggregate_errored` | int | 錯誤數 |
| `coverage_pct` | float | 測試覆蓋率 |
| `test_exit_code` | int | pytest 結束碼 |

#### review.json — LLM 分析

LLM 比對新舊程式碼 + 測試結果，產出語意分析和風險評估。即使所有測試通過，也可能有未被測試覆蓋的風險。

```json
{
  "run_id": "test_result",
  "modules": [
    {
      "before_files": ["Python/Leaderboard/leaderboard.py"],
      "after_files": ["Python/Leaderboard/leaderboard.py"],
      "semantic_diff": "No behavioral changes detected; both versions implement identical logic.",
      "test_purpose": "Verify Driver, Race scoring, and Leaderboard ranking produce identical outputs.",
      "result_analysis": "All tests passed. Coverage at 86% covers main logic paths.",
      "failures_ignorable": false,
      "ignorable_reason": null,
      "risk_warnings": [
        {
          "description": "Tie-breaking in rankings depends on dict insertion order",
          "severity": "medium",
          "tested_by_golden": true
        }
      ]
    }
  ],
  "overall_assessment": "Reviewed 1 module(s). No high-severity risks detected."
}
```

##### modules[i] 欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `semantic_diff` | string | 新舊 code 的行為差異分析 |
| `test_purpose` | string | 測試目的說明 |
| `result_analysis` | string | 測試結果點評（失敗原因、是否為基礎設施問題等） |
| `failures_ignorable` | bool | 失敗是否可忽略 |
| `ignorable_reason` | string\|null | 可忽略的原因說明 |
| `risk_warnings` | array | 風險清單 |
| `risk_warnings[].description` | string | 風險描述 |
| `risk_warnings[].severity` | string | low / medium / high / critical |
| `risk_warnings[].tested_by_golden` | bool | 是否已被 golden test 覆蓋 |

##### 三個檔案的關係

```
summary.json          test_records.json         review.json
─────────────         ─────────────────         ───────────
pass_rate: 100%       每個 test item 的          "但有 1 個 medium
coverage: 86%         golden output + 狀態         risk 需注意"

  ↓ 快速判斷             ↓ 需要細節時看              ↓ 做最終決策
  pass / fail            debug / 追溯              是否接受重構
```

#### Golden Output 格式說明

Golden output 的 key 是 LLM 決定的描述性命名，代表「測試什麼 + 預期值」：

```json
{
  "Race_points_first_place": 25,
  "Race_points_second_place": 18,
  "Race_driver_name_human": "Charles",
  "Leaderboard_driver_points_full_season": {
    "Max": 58,
    "Charles": 43
  }
}
```

| Key 格式 | 含意 |
|----------|------|
| `ClassName_methodName_scenario` | 類別方法測試 |
| `functionName_scenario` | 函式測試 |

### Golden Output 生成與使用流程

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Golden Capture（只跑一次，舊 code）                   │
│                                                               │
│ LLM 讀舊 code → 決定測什麼 → 生成 keys + 執行得到 values      │
│                                                               │
│ 輸出: {"Race_points_first": 25, "Leaderboard_rank": [...]}   │
└──────────────────────────────────────────────────────────────┘
                              ↓
                     keys + values 傳遞
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Test Emit（新 code）                                  │
│                                                               │
│ LLM 讀新 code + golden output (keys+values)                  │
│ → 根據 key 的語意找新 code 中對應的功能                       │
│ → 生成 test 驗證新功能的輸出 == golden value                  │
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

#### 潛在優化方向

```
選項 A: 雙向對應
┌─────────────┐     ┌─────────────┐
│ 舊 code     │     │ 新 code     │
│ 5 個測試項  │ ←→  │ 7 個測試項  │
└─────────────┘     └─────────────┘
        ↓                 ↓
     找交集：能對應的項目 + 報告差異

選項 B: Function Signature 對應
- 不依賴 LLM 命名的 key
- 用 AST 分析 function input/output type 自動對應
- 更穩定但實作複雜

選項 C: 接受部分覆蓋（目前做法）
- Golden 決定要測什麼
- 新 code 盡量對應
- 無法對應的就跳過 + 在報告中標示
```

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

| Plugin | Golden Script 執行 | Test 執行 | Coverage 工具 |
|--------|-------------------|-----------|--------------|
| `PythonPlugin` | `coverage run script.py` | `pytest + coverage` | coverage.py |
| `GoPlugin` | `go run script.go` | `go test -cover` | go tool cover |
| `JavaPlugin` | `java Script.java` | `mvn test` | JaCoCo |

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
│       ├── plugins/        # Language plugins
│       ├── main.py         # API 入口
│       ├── golden_capture.py
│       ├── test_emitter.py
│       ├── test_runner.py
│       └── ...
├── eval/                   # Metrics, scoring
├── web/                    # React frontend
├── shared/                 # Shared schemas
├── scripts/                # Dev scripts
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
