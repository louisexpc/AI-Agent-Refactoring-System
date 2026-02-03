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

#### stage_report.json (摘要)

```json
{
  "run_id": "test_result",
  "records": [
    {
      "module_mapping": {
        "before_files": ["Python/Leaderboard/leaderboard.py"],
        "after_files": ["Python/Leaderboard/leaderboard.py"]
      },
      "golden_records": [
        {
          "file_path": "Python/Leaderboard/leaderboard.py",
          "output": {
            "Race_points_first_place": 25,
            "Leaderboard_driver_rankings": ["Max", "Charles"]
          },
          "exit_code": 0,
          "coverage_pct": 100.0
        }
      ],
      "test_result": {
        "total": 6,
        "passed": 6,
        "failed": 0,
        "errored": 0,
        "coverage_pct": 86.05
      },
      "tested_functions": [
        "Race_points_first_place",
        "Leaderboard_driver_rankings"
      ],
      "golden_script_path": "golden/Python_Leaderboard_leaderboard_py_script.py",
      "emitted_test_path": "tests/test_leaderboard.py"
    }
  ],
  "overall_pass_rate": 1.0,
  "overall_coverage_pct": 86.05,
  "build_success": true
}
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
