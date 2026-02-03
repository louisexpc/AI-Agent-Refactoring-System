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
├── summary.json              # 精簡報告
├── stage_report.json         # 完整測試報告
├── golden/                   # Golden capture 產物
│   ├── *_script.py           # LLM 生成的呼叫腳本
│   ├── *.coverage            # Coverage 資料
│   └── *.log                 # 執行日誌
└── tests/                    # 生成的測試檔案
    ├── test_*.py             # Pytest 測試檔
    └── *.log                 # 測試執行日誌
```

#### summary.json

```json
{
  "run_id": "test_result",
  "build_success": true,
  "overall_pass_rate": 1.0,
  "overall_coverage_pct": 86.05,
  "total_modules": 1,
  "total_passed": 6,
  "total_failed": 0,
  "total_errored": 0
}
```

#### stage_report.json 完整欄位說明

```json
{
  "run_id": "test_result",
  "records": [...],
  "overall_pass_rate": 1.0,
  "overall_coverage_pct": 86.05,
  "build_success": true
}
```

##### 頂層欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `run_id` | string | 本次執行的唯一識別碼 |
| `records` | array | 每個 module mapping 的測試結果（詳見下方） |
| `overall_pass_rate` | float | 所有測試的通過率 (0.0~1.0)，計算方式：`總 passed / 總 tests` |
| `overall_coverage_pct` | float | 所有 module 的平均行覆蓋率 |
| `build_success` | bool | 新程式碼是否能成功編譯（用 `python -m compileall` 檢查） |

##### records[i] - 單一 Module 的測試結果

```json
{
  "module_mapping": {...},
  "golden_records": [...],
  "emitted_test_file": {...},
  "test_result": {...},
  "coverage_pct": 86.05,
  "tested_functions": [...],
  "golden_script_path": "golden/..._script.py",
  "emitted_test_path": "tests/test_xxx.py"
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `module_mapping` | object | 這組測試對應的 before/after 檔案映射 |
| `golden_records` | array | 執行舊程式碼得到的 golden output（可能有多筆） |
| `emitted_test_file` | object | LLM 生成的測試檔案內容 |
| `test_result` | object | 執行測試檔案的結果 |
| `coverage_pct` | float | 本 module 的行覆蓋率 |
| `tested_functions` | array | Golden output 中的所有 key（代表測了哪些功能） |
| `golden_script_path` | string | Golden capture 腳本的相對路徑 |
| `emitted_test_path` | string | 生成的測試檔案的相對路徑 |

##### module_mapping - 檔案映射

```json
{
  "before_files": ["Python/Leaderboard/leaderboard.py"],
  "after_files": ["Python/Leaderboard/leaderboard.py"]
}
```

| 欄位 | 說明 |
|------|------|
| `before_files` | 舊 repo 中的檔案路徑（用來生成 golden output） |
| `after_files` | 新 repo 中的檔案路徑（被測試的對象） |

##### golden_records[i] - Golden Output 記錄

```json
{
  "file_path": "Python/Leaderboard/leaderboard.py",
  "output": {
    "Race_points_first_place": 25,
    "Leaderboard_driver_rankings": ["Max", "Charles"]
  },
  "exit_code": 0,
  "stderr_snippet": null,
  "duration_ms": 176,
  "coverage_pct": 100.0
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `file_path` | string | 對應的來源檔案 |
| `output` | object | **Golden Output 核心資料**：key 是測試項目描述，value 是執行舊程式碼的結果 |
| `exit_code` | int | Golden capture 腳本的結束碼（0=成功） |
| `stderr_snippet` | string | 錯誤輸出片段（debug 用） |
| `duration_ms` | int | 執行時間（毫秒） |
| `coverage_pct` | float | 執行 golden capture 時的行覆蓋率 |

##### emitted_test_file - LLM 生成的測試檔

```json
{
  "path": "Python/Leaderboard/test_leaderboard.py",
  "language": "python",
  "content": "import sys\nimport pytest\n...",
  "source_file": "Python/Leaderboard/leaderboard.py"
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `path` | string | 測試檔案的路徑（相對於 module） |
| `language` | string | 目標語言（python/go/java） |
| `content` | string | **完整的測試程式碼**（LLM 生成，包含 golden values 的 assert） |
| `source_file` | string | 測試對應的來源檔案 |

##### test_result - 測試執行結果

```json
{
  "test_file": "Python/Leaderboard/test_leaderboard.py",
  "total": 6,
  "passed": 6,
  "failed": 0,
  "errored": 0,
  "coverage_pct": 86.05,
  "stdout": "===== test session starts =====\n...",
  "stderr": "...",
  "exit_code": 0
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `test_file` | string | 執行的測試檔案 |
| `total` | int | 測試案例總數 |
| `passed` | int | 通過的測試數 |
| `failed` | int | 失敗的測試數（assert 不通過） |
| `errored` | int | 錯誤的測試數（執行時 exception） |
| `coverage_pct` | float | 測試覆蓋率 |
| `stdout` | string | pytest 的標準輸出（包含測試結果） |
| `stderr` | string | pytest 的錯誤輸出 |
| `exit_code` | int | pytest 結束碼（0=全部通過，1=有失敗，2=錯誤） |

##### 欄位關係圖

```
stage_report.json
├── run_id                     # 執行識別碼
├── build_success              # 編譯是否成功
├── overall_pass_rate          # 總通過率
├── overall_coverage_pct       # 總覆蓋率
└── records[]                  # 每個 module 的結果
    ├── module_mapping         # 哪些檔案被測試
    │   ├── before_files       # 舊檔案（產生 golden）
    │   └── after_files        # 新檔案（被驗證）
    ├── golden_records[]       # Golden capture 結果
    │   ├── output             # {key: value} 的 golden values
    │   ├── exit_code          # 執行是否成功
    │   └── coverage_pct       # 舊程式碼覆蓋率
    ├── emitted_test_file      # LLM 生成的測試
    │   ├── content            # 測試程式碼（含 assert golden values）
    │   └── language           # 目標語言
    ├── test_result            # 測試執行結果
    │   ├── passed/failed      # 通過/失敗數
    │   ├── coverage_pct       # 新程式碼覆蓋率
    │   └── stdout             # pytest 輸出
    └── tested_functions       # golden output 的 keys 清單
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
from runner.test_gen import run_characterization_test, run_stage_test
from runner.test_gen.llm_adapter import create_vertex_client

# 建立 LLM client
llm_client = create_vertex_client()

# 單一 module 測試
record = run_characterization_test(
    run_id="test_001",
    repo_dir=Path("path/to/old/code"),
    refactored_repo_dir=Path("path/to/new/code"),
    before_files=["src/leaderboard.py"],
    after_files=["pkg/leaderboard.go"],
    dep_graph=dep_graph,
    llm_client=llm_client,
    artifacts_root=Path("artifacts"),
    source_language="python",
    target_language="go",
)

# 整個 Stage 測試
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
