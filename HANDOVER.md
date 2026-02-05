# Generate Test 模組使用說明

## 快速開始

### 1. 準備輸入檔案

準備以下檔案（**預設使用 mapping_1.json**）：

| 檔案 | 預設路徑 | 說明 |
|------|---------|------|
| **Mapping 設定** | `scripts/mapping_1.json` | 定義 before/after 檔案對應 |
| **Dep Graph** | `artifacts/f3f7dfdffa4940d185668190b7a28b05/depgraph/dep_graph.json` | 依賴圖 |
| **原始碼** | `artifacts/f3f7dfdffa4940d185668190b7a28b05/snapshot/repo` | 舊程式碼 (before) |
| **重構後程式碼** | `.` (專案根目錄) | 新程式碼 (after)，包含 `refactor/` 資料夾 |

**mapping_1.json** 對應模組：`refactor/telemetry/`（Python → Go）

#### mapping_1.json 內容

```json
{
  "source_language": "python",
  "target_language": "go",
  "repo_dir": "artifacts/f3f7dfdffa4940d185668190b7a28b05/snapshot/repo",
  "refactored_repo_dir": ".",
  "dep_graph_path": "artifacts/f3f7dfdffa4940d185668190b7a28b05/depgraph/dep_graph.json",
  "mappings": [
    {
      "before": ["Python/TelemetrySystem/client.py", "Python/TelemetrySystem/telemetry.py", "Python/TelemetrySystem/test_telemetry.py"],
      "after": ["refactor/telemetry/telemetry.go", "refactor/telemetry/telemetry_test.go"]
    }
  ]
}
```

### 2. 設定 GCP 認證

Generate Test 使用 Vertex AI Gemini 2.5 Pro，需要 GCP service account key。

**方法 1：設定環境變數（推薦）**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-gcp-key.json"
```

**方法 2：修改預設路徑**

編輯 `runner/test_gen/llm_adapter.py:25-26`，將 `_DEFAULT_KEY_PATH` 改成你的 key 檔案路徑：

```python
_DEFAULT_KEY_PATH = Path("/your/path/to/gcp-key.json")
```

### 3. 執行測試生成

```bash
uv run python -m scripts.test_e2e_characterization
```

**修改 Mapping 檔案**：編輯 `scripts/test_e2e_characterization.py:31`

```python
MAPPING_FILE = PROJECT_ROOT / "scripts/mapping_1.json"  # 改成你的 mapping
```

### 4. 查看輸出結果

執行完成後，產出會在：

```
artifacts/test_result/
├── summary.json           # 統計摘要（通過率、覆蓋率、build 狀態）
├── test_records.json      # 完整測試記錄（golden output + test items）
├── review.json            # LLM 分析（semantic diff + 風險評估）
├── golden/                # Golden capture 腳本和輸出
│   └── module_0_golden.py
└── tests/                 # 生成的測試檔案
    ├── conftest.py
    ├── module_0_test.go
    └── *.log
```

**輸出 ID 修改**：編輯 `scripts/test_e2e_characterization.py:30`

```python
RUN_ID = "test_result"  # 改成你想要的名稱
```
