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

### 已實作模組

| 檔案 | 說明 |
|------|------|
| `main.py` | Orchestrator（公開 API: `run_stage_test`） |
| `plugins/` | Language plugins (Python/Go/Java) |
| `golden_capture.py` | 執行舊 code 收集 golden output |
| `test_emitter.py` | LLM 生成 test file |
| `test_runner.py` | 執行 test file + 解析個別 test item 結果 |
| `guidance_gen.py` | LLM 分析產出測試指引 |
| `review_gen.py` | LLM semantic diff + 風險評估 |
| `dep_resolver.py` | 依賴 signatures 提取 |
| `llm_adapter.py` | Vertex AI Gemini adapter (含 429 retry) |
| `report_builder.py` | 建立 summary / test_records / review |

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
├── test_records.json     # 事實：golden output + 每個 test item 狀態
├── review.json           # LLM 分析：semantic diff + 風險評估
├── golden/               # golden capture 產物
└── tests/                # 生成的測試檔
```

## Coding Style

- `ruff format` 統一格式
- Type hints + Google style docstrings
- Python 3.12

## 執行測試

```bash
uv run python -m scripts.test_e2e_characterization
```
