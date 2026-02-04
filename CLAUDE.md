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

### 處理流程

```
For each module mapping:
  Phase 1: Guidance → LLM 分析 side effects / mock recommendations
  Phase 2: Golden Capture → LLM 生成腳本 → 執行舊 code → JSON golden output
  Phase 3: Test Emit → LLM 讀新 code + golden values → 生成 pytest test file
  Phase 4: Test Run → pytest + coverage → 解析 test items + failure_reason

Then:
  Build Check → compileall
  Review → LLM semantic diff + risk warnings + per-test-item 點評
  Output → summary.json + test_records.json + review.json
```

### DepGraph 用途

- dep_graph 提供依賴 **edges**（哪個檔案 import 哪個檔案）
- `dep_resolver.py` 根據 edges 定位依賴檔案，用 AST 提取 **signatures**（class/function 簽名，不含 body）
- Signatures 傳給 LLM 作為 context

### 已實作模組

| 檔案 | 說明 |
|------|------|
| `main.py` | Orchestrator（公開 API: `run_stage_test`） |
| `plugins/` | Language plugins (Python/Go/Java) |
| `golden_capture.py` | 執行舊 code 收集 golden output |
| `test_emitter.py` | LLM 生成 test file |
| `test_runner.py` | 執行 test file + 解析 test items + failure_reason |
| `guidance_gen.py` | LLM 分析產出測試指引 |
| `review_gen.py` | LLM semantic diff + per-test-item 點評 + 風險評估 |
| `dep_resolver.py` | DepGraph 依賴 signatures 提取 (AST) |
| `llm_adapter.py` | Vertex AI Gemini adapter (含 429 retry) |
| `report_builder.py` | 建立 summary / test_records |

### API 介面

```python
from runner.test_gen import run_stage_test

report = run_stage_test(
    run_id, repo_dir, refactored_repo_dir,
    stage_mappings, dep_graph, llm_client,
    artifacts_root, source_language, target_language
)
```

### Artifact 輸出

```
artifacts/<run_id>/
├── summary.json          # 統計數據 + build 狀態
├── test_records.json     # 事實：golden output + test items + failure_reason
├── review.json           # LLM 分析：semantic diff + risk warnings + per-test-item 點評
├── golden/               # golden capture 產物
└── tests/                # 生成的測試檔 + conftest.py + log
```

### 關鍵實作細節

- **PYTHONPATH 注入**：source_dirs → Python/ → work_dir → 既有 PYTHONPATH
- **conftest.py**：自動生成，將 source_dirs 插入 sys.path 最前面（優先於 cwd）
- **failure_reason 解析**：從 pytest short summary + ERRORS section 雙重解析
- **review 粒度**：semantic_diff / risk_warnings 是 per-module，test_item_reviews 是 per-test-item

## Coding Style

- `ruff format` 統一格式
- Type hints + Google style docstrings
- Python 3.12

## 執行測試

```bash
uv run python -m scripts.test_e2e_characterization
```
