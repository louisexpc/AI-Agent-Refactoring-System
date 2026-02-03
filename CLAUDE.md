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

**策略**：Characterization Testing（執行舊 code → golden output → 驗證新 code）

### 已實作模組

| 檔案 | 說明 |
|------|------|
| `main.py` | API 入口 (`run_characterization_test`, `run_stage_test`) |
| `plugins/` | Language plugins (Python/Go/Java) |
| `golden_capture.py` | 執行舊 code 收集 golden output |
| `test_emitter.py` | LLM 生成 test file |
| `test_runner.py` | 執行 test file |
| `guidance_gen.py` | LLM 分析產出測試指引 |
| `dep_resolver.py` | 依賴 signatures 提取 |
| `llm_adapter.py` | Vertex AI Gemini adapter (含 429 retry) |
| `report_builder.py` | 建立 stage report |

### API 介面

```python
from runner.test_gen import run_characterization_test, run_stage_test

# 單一 module
record = run_characterization_test(
    run_id, repo_dir, refactored_repo_dir,
    before_files, after_files, dep_graph,
    llm_client, artifacts_root,
    source_language, target_language
)

# 整個 Stage
report = run_stage_test(
    run_id, repo_dir, refactored_repo_dir,
    stage_mappings, dep_graph, llm_client,
    artifacts_root, source_language, target_language
)
```

### Artifact 輸出

```
artifacts/<run_id>/
├── summary.json          # 精簡報告
├── stage_report.json     # 完整報告
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
