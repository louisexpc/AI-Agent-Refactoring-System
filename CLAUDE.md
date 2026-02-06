# AI Context - TSMC 2026 Hackathon

AI 輔助舊程式碼重構系統。詳細文件請見 README.md。

## 專案概述

自動化重構 pipeline：Repo URL → Analyze & Plan → Stage-based 重構 → Generate Test → 迭代改善

## 模組分工

| 模組 | 負責人 | 路徑 |
|------|--------|------|
| Repo Loader | Louis | - |
| Analyze & Plan | Jesse, Karl | - |
| **Generate Test** | Yoyo | `runner/test_gen/` |

## Generate Test 模組 (runner/test_gen/)

**策略**：Characterization Testing（執行舊 code → golden output → 驗證新 code）+ LLM Semantic Diff

### 處理單位

- **Module**：一組 before/after 檔案的對應（1~N 個檔案）
- 整個 module 的所有檔案**聚合成一份原始碼**送 LLM
- 每個 module 產出一個 golden script 和一個 test file

### 處理流程（5-Stage Pipeline）

```
For each module mapping:
  Stage 1: Generate Golden
    - LLM 生成 guidance（side effects / mock recommendations）
    - LLM 生成 golden script（執行舊 code 的腳本）
    - LLM 生成 execute_golden.sh 和 requirements.txt
    - 輸出：golden script + sh + requirements（不執行）

  Stage 2: Execute Golden（Docker/Sandbox）
    - 在隔離環境執行 execute_golden.sh
    - 收集 golden output（JSON）
    - 寫入 logs/golden_execution.log

  Stage 3: Generate Tests
    - LLM 讀取 golden output + 新 code
    - LLM 生成 test file
    - LLM 生成 execute_test.sh 和 requirements.txt
    - 輸出：test file + sh + requirements（不執行）

  Stage 4: Execute Tests（Docker/Sandbox）
    - 在隔離環境執行 execute_test.sh
    - 收集測試結果（test items + failure_reason + coverage）
    - 寫入 logs/test_execution.log

  Stage 5: Generate Reports
    - Build Check（compileall）
    - LLM Review（semantic diff + risk warnings + per-test-item 點評）
    - 輸出：summary.json + test_records.json + review.json
```

**特點**：
- 生成（Stage 1, 3）與執行（Stage 2, 4）分離
- 支援 Docker/Sandbox 隔離執行（可選）
- LLM 動態生成執行腳本和依賴檔案
- 捕獲執行 log 供調試

### DepGraph 用途

- dep_graph 提供依賴 **edges**（哪個檔案 import 哪個檔案）
- `dep_resolver.py` 根據 edges 定位依賴檔案，用 AST 提取 **signatures**（class/function 簽名，不含 body）
- Signatures 傳給 LLM 作為 context

### 已實作模組

| 檔案 | 說明 |
|------|------|
| `main.py` | Orchestrator（Stage functions + 舊 API `run_stage_test`） |
| `pipeline_tool.py` | LangGraph `@tool` 入口 + 5-Stage pipeline（含 Docker 整合） |
| `plugins/` | Language plugins (Python/Go/Java) |
| `golden_capture.py` | 執行舊 code 收集 golden output |
| `test_emitter.py` | LLM 生成 test file |
| `test_runner.py` | 執行 test file + 解析 test items + failure_reason |
| `guidance_gen.py` | LLM 分析產出測試指引 |
| `review_gen.py` | LLM semantic diff + per-test-item 點評 + 風險評估 |
| `dep_resolver.py` | DepGraph 依賴 signatures 提取 (AST) |
| `llm_adapter.py` | Vertex AI Gemini adapter (含 429 retry) |
| `report_builder.py` | 建立 summary / test_records |

### Workspace 目錄結構

```
workspace/
  init/
    <SHA256>/
      depgraph/           # dep_graph.json
      repo/               # Clone, 只讀
  refactor_repo/          # 重構後 code（持續 commit）
  stage_<i>/
    stage_plan/
      stage_<i>.md
      mapping_<i>.json
      test_result/        # ← Generate Test 輸出
        golden/
        test/
        logs/
        summary.json
        test_records.json
        review.json
  final_report/
```

### API 介面

```python
# LangGraph tool（agent 使用，推薦）
from runner.test_gen.pipeline_tool import generate_test
tools = [generate_test]

# Agent 呼叫時只需傳 mapping_path：
# generate_test.invoke({
#     "mapping_path": "workspace/stage_1/stage_plan/mapping_1.json",
#     "use_sandbox": False,
# })
# → 回傳 JSON string: {"ok": true, "test_result_dir": "...", "summary_path": "...", ...}

# Python 直接呼叫（不透過 agent）
from runner.test_gen.pipeline_tool import run_characterization_pipeline

result = run_characterization_pipeline(
    run_id="stage_1",
    test_result_dir="workspace/stage_1/stage_plan/test_result",
    repo_dir="workspace/init/<SHA256>/repo",
    refactored_repo_dir="workspace/refactor_repo",
    mappings=[{"before": [...], "after": [...]}],
    dep_graph_path="workspace/init/<SHA256>/depgraph/dep_graph.json",
    llm_client=llm_client,
    source_language="python",
    target_language="go",
    use_sandbox=True,
)

# 舊 API（向下相容）
from runner.test_gen import run_stage_test
```

### Artifact 輸出

```
test_result/
├── golden/               # Stage 1: golden script + sh + requirements
├── test/                 # Stage 3: test file + sh + requirements
├── logs/                 # Stage 2/4: Docker 執行 log
│   ├── golden_execution.log
│   └── test_execution.log
├── summary.json          # Stage 5: 統計數據 + build 狀態
├── test_records.json     # Stage 5: golden output + test items + failure_reason
└── review.json           # Stage 5: semantic diff + risk warnings + per-test-item 點評
```

### 關鍵實作細節

- **PYTHONPATH 注入**：source_dirs → Python/ → work_dir → 既有 PYTHONPATH
- **conftest.py**：自動生成，將 source_dirs 插入 sys.path 最前面（優先於 cwd）
- **failure_reason 解析**：從 pytest short summary + ERRORS section 雙重解析
- **review 粒度**：semantic_diff / risk_warnings 是 per-module，test_item_reviews 是 per-test-item
- **LLM 生成 sh/requirements**：plugins 呼叫 LLM 分析 imports 動態生成

## Coding Style

- `ruff format` 統一格式
- Type hints + Google style docstrings
- Python 3.12

## 執行測試

```bash
# Pipeline 測試（不使用 Docker）
uv run python -m scripts.test_pipeline

# 舊版 E2E 測試
uv run python -m scripts.test_e2e_characterization
```
