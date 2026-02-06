# LangGraph `generate_test` Tool 使用指引

## 1. 匯入 Tool

```python
from runner.test_gen.pipeline_tool import generate_test

# 建立 LangGraph agent 時加入 tools
tools = [generate_test]
```

## 2. Mapping JSON 格式

Tool 需要一個 `mapping_path` 指向 JSON 檔案，格式如下：

```json
{
  "repo_dir": "workspace/init/<SHA256>/repo",
  "refactored_repo_dir": "workspace/refactor_repo",
  "dep_graph_path": "workspace/init/<SHA256>/depgraph/dep_graph.json",
  "source_language": "python",
  "target_language": "go",
  "mappings": [
    {
      "before": ["src/old_module.py"],
      "after": ["src/new_module.go"]
    }
  ]
}
```

## 3. Agent 呼叫方式

```python
# Agent 只需傳 mapping_path（必要）+ use_sandbox（選填）
result = generate_test.invoke({
    "mapping_path": "workspace/stage_1/stage_plan/mapping_1.json",
    "use_sandbox": False,  # True = 使用 Docker 執行
})
```

## 4. 回傳值

回傳 JSON string，需自行 `json.loads()` 解析：

```json
// 成功
{
  "ok": true,
  "test_result_dir": "workspace/.../test_result",
  "summary_path": "workspace/.../test_result/summary.json",
  "test_records_path": "workspace/.../test_result/test_records.json",
  "review_path": "workspace/.../test_result/review.json"
}

// 失敗
{
  "ok": false,
  "error": "Mapping file not found: ..."
}
```

## 5. 完整 LangGraph 範例

```python
from langchain_google_vertexai import ChatVertexAI
from langgraph.prebuilt import create_react_agent
from runner.test_gen.pipeline_tool import generate_test

# 建立 agent
llm = ChatVertexAI(model="gemini-2.0-flash")
agent = create_react_agent(llm, tools=[generate_test])

# 執行
response = agent.invoke({
    "messages": [
        ("user", "請對 mapping_1.json 執行 characterization testing")
    ]
})
```

## 6. 參數說明

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `mapping_path` | str | (必填) | Mapping JSON 檔案路徑 |
| `use_sandbox` | bool | `False` | 是否使用 Docker sandbox 執行 |
| `sandbox_image` | str | `"hack-sandbox:latest"` | Docker image 名稱 |

## 7. 輸出目錄結構

執行後會在 `mapping_path` 同層產生 `test_result/`：

```
test_result/
├── golden/           # Stage 1: golden script
├── test/             # Stage 3: test file
├── logs/             # Stage 2/4: 執行 log
├── summary.json      # 統計
├── test_records.json # golden output + test items
└── review.json       # semantic diff + 風險評估
```
## 9. GCP 認證設定

Generate Test 使用 Vertex AI Gemini，需要 GCP 認證：

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-gcp-key.json"
```

或修改 `runner/test_gen/llm_adapter.py` 中的 `_DEFAULT_KEY_PATH`。
