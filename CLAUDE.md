# 題目 : AI 舊程式碼智能重構，可量化AI輔助系統，實現迭代翻新
##  三個要解決的Project
Project1:熱門語言寫出來的CLI工具，代碼規模12K+，要refactor成某語言(也可能是本身)
  主要測試邏輯正確性和Test Coverage
  邏輯正確性(70%)
  Test Coverage(30%)

Project2:MVC架構，由後端渲染HTML，為早年流行的架構，現在該語言開發者少，但專案仍具有價值，期望以現代語言重構成前後端分離的架構
  主要測試Agent對於非主流語言的轉換能力，以及是否可以將UI從後端邏輯集裡面撥離出
  後端重構成其他語言(50%)
  前端重構成其他語言(50%)

Project3:經典購物車系統，由熱門語言撰寫
  主要測試弱型別語言轉強型別語言Agent要可以理解不同類席資料庫的差異，並妥善轉成RAW SQL
  Backend重構成強型別(70%)
  所有的RAW SQL都要可以被測試覆蓋(30%)

- 只可以輸入init prompt和start prompt
- 輸入 : repo網址&prompt
- 輸出 : 每輪迭代需產出重構評估報告、下輪計畫
- UI不限格式，可以是CLI、Web等等
- 平台 : GCP
## 迭代前 Pipeline
### Repo Loader (Louis)
- Target: Clone All files + PR 報告 -> Local Cache + Indexing Database(or method)
- 對外 API : 接 `repo_url` + `prompt`(Optional)
- AST (依賴性分析)
### Analyze & Plan (Jesse, Karl)
- Target: Agent 分析整體 repo + 重構計畫
- 提供一個 Prompt Template 引導重構方向 + 人工調整 Prompt
Recommendations:
- 分析 Module Dependency 決定改訂計畫 + Test Cases 測試
### Generate Test (Yoyo)
- 策略：Golden Master / Snapshot Testing + Unit Test 雙層驗證
- 對外 API：`run_test_generation()` 單一入口，供迭代 pipeline 呼叫
- 呼叫方透過傳入不同的 `dep_graph` 範圍控制測試全 repo 或單一 module
- 所有 LLM 依賴的模組在 `llm_client=None` 時都有 stub fallback

#### 測試流程
```
迭代前（iteration=0, refactored_repo_dir=None）:
  Phase 1-3b → 建立 golden baseline
  Phase 5    → emit unit test 檔案
  Phase 5b   → 執行 unit tests 收集 coverage

每輪迭代（iteration=1,2,3..., refactored_repo_dir=重構後目錄）:
  ① Phase 5b: 跑 unit test（對重構後 code）→ pass/fail + coverage
  ② Phase 4:  跑 golden comparison（新舊 code 輸出 diff）→ 行為是否改變
  ③ Phase 6:  合併報告：unit test results + golden comparison results
```

#### Phase 說明
**Phase 1：識別 Entry Points**
- 從 RepoIngestion 的 DepGraphL0 + 原始碼用 regex 提取可測函式
- 支援 .py/.go/.js/.ts，識別 function/method signature
- 輸入資料（來自 RepoIngestion）：
    - DepGraphL0: nodes(DepNode[]) + edges(DepEdge[])
    - DepNode: node_id, path, kind
    - DepEdge: src, dst, kind, confidence

**Phase 2：LLM 生成測試指引（Guidance）**
- LLM 分析每個模組原始碼，產出結構化 JSON 指引
- 內容：副作用識別（file I/O, network, DB）、mock 建議、非確定性行為（時間戳、隨機數）、外部依賴

**Phase 3：LLM 生成測試輸入（Input Gen）**
- LLM 讀 function signature + docstring + guidance → 產生測試案例
- 每個 entry 至少 3 筆：正常路徑、邊界值、錯誤處理

**Phase 3b：Golden Capture**
- LLM 生成可執行 Python 腳本（處理 class 實例化、mock 副作用依賴）
- subprocess 執行舊 code，捕獲 stdout 作為 golden output

**Phase 4：Golden Comparison（迭代時才執行）**
- 用同樣 inputs 跑重構後 code，normalize 後 diff 新舊輸出
- OutputNormalizer 清洗時間戳、UUID 等非確定性欄位

**Phase 5：Test Code Emitter**
- LLM 根據 TestInput + GoldenRecord 產出目標語言的可執行測試檔（pytest/go test/jest）

**Phase 5b：Test Runner（執行 Unit Tests）**
- subprocess 跑 pytest 執行 emitted 測試檔案
- 收集 pass/fail 數量 + pytest-cov coverage 百分比

**Phase 6：Report Builder**
- 合併 golden comparison results + unit test results
- 統計 pass/fail/error/skipped + pass_rate + coverage_pct

#### 對外 API
```python
from runner.test_gen import run_test_generation

report = run_test_generation(
    run_id="some_run_id",
    repo_dir=Path("path/to/legacy/code"),
    dep_graph=dep_graph,            # RepoIngestion 的 DepGraphL0
    repo_index=repo_index,          # RepoIngestion 的 RepoIndex
    exec_matrix=exec_matrix,        # RepoIngestion 的 ExecMatrix
    artifacts_root=Path("artifacts"),
    llm_client=llm_client,          # VertexLLMClient 或 None
    iteration=0,                    # 0=迭代前, 1+=迭代中
    refactored_repo_dir=None,       # 迭代時傳入重構後目錄
    target_language="python",       # python/go/typescript
)
# report.total, report.passed, report.failed, report.pass_rate
# report.coverage_pct, report.unit_test_results, report.results
# report.emitted_files
```

#### Artifact 輸出
```
artifacts/<run_id>/test_gen/
├── entries.json           # Phase 1: 可測 entry points
├── guidance.json          # Phase 2: 測試指引
├── inputs.json            # Phase 3: 測試輸入
├── golden_snapshot.json   # Phase 3b: golden output
├── test_report.json       # Phase 6: 最終報告
└── emitted/               # Phase 5: 可執行測試檔
    ├── test_sensor.py
    └── ...
```

#### 待優化
- coverage 目標門檻設定（配合整體 75% 要求）
- 針對不同語言特性的測試優化（型別系統、錯誤處理模式）
- 整合 git diff 資訊輔助精準測試
## 迭代 Pipeline(尚未實作)
- Package : LanGraph
Iterative Loop：Analyze → Plan → Apply → Validate → Report → Decide → 下一輪/停止
---
### Analyze & Plan
- Input: 上輪 report + Init Plan，
- Output: 本輪 tasks（分優先序與風險）
- Metrics
    - 每輪計畫可執行率（plan→apply 成功比例）
    - 任務粒度（每輪平均改動檔案數/LOC）
---
### Apply(修改Code)
- Tool: Git/OS/Coding Style Tool/DB API
- Input: Task from `Analyze & Plan`
- Output: Commit on Repo + Reports
---
### Validate
- Unit Test + General Test
- Metrics:
    - Line Coverage
- Output: Test Report + Validation Score
### Fallback(暫定要加)
- 觸發: Test Case 通過率低於上一輪(暫定) or Line Coverage 降低
---
### Report
- 產出本輪報告 + 下輪 Start Prompt
### Criteria & Limitation(暫定)
- Can Build/Compile
- Coverage Ratio: 75%
    - Early Stopping Mechnism
- Time Limit: 15 min per iteration
- Token Limit: 50 K per interation
- Maximun Iteration : 3

# Coding Style
- `ruff format`: 維護統一 coding style
- 註解 + 參數 `typing` 設定
    ```python
    def method(args: List, arg2: Dict)-> str:
        ```
        docstrings: Recommendation : Google Python Style Guide
        ```
    ```
#   問題&想法(還不實作)
- 記憶庫機制 (Refactor Memory)
為解決 LLM 在長流程中的遺忘問題，維護一個輕量級 RAGJSON 檔：
**內容**：Key 為 Python 原始函式名，Value 為重構後的 Go 函式簽名。
**用途**：當重構上層業務邏輯 (Level N) 時，直接查表獲取底層 (Level N-1) 的正確呼叫方式，避免參數不匹配。
- 循環依賴處理 (Dependency Inversion)
- 視覺化演示設計 (For Demo)
- 在儀表板中實作互動式圖表：
**動態節點**：正在重構的檔案節點會閃爍或高亮顯示。
**顏色編碼**：灰色 (Pending) -> 黃色 (Processing) -> 紅色 (Error) -> 綠色 (Done)。
**目的**：讓評審直觀理解運作過程。
- Lrgacy code如果根本跑不起來?要怎麼驗證?
#   實作更新
模組實作：

- `runner/test_gen/__init__.py` — 匯出 `run_test_generation`
- `runner/test_gen/entry_detector.py` — Phase 1: regex 提取可測函式（支援 .py/.go/.js/.ts）
- `runner/test_gen/guidance_gen.py` — Phase 2: LLM 生成測試指引
- `runner/test_gen/input_gen.py` — Phase 3: LLM 生成測試輸入
- `runner/test_gen/golden_capture.py` — Phase 3b: LLM 生成呼叫腳本 + subprocess 捕獲 golden output
- `runner/test_gen/output_normalizer.py` — 清洗時間戳/UUID 等非確定性欄位
- `runner/test_gen/golden_comparator.py` — Phase 4: normalize 後 diff 新舊輸出
- `runner/test_gen/test_emitter.py` — Phase 5: 產出可執行測試檔（pytest/go test/jest）
- `runner/test_gen/test_runner.py` — Phase 5b: subprocess 跑 pytest 收集 pass/fail + coverage
- `runner/test_gen/report_builder.py` — Phase 6: 統計 pass/fail/coverage
- `runner/test_gen/main.py` — Orchestrator，串接所有 phase
- `runner/test_gen/llm_adapter.py` — Vertex AI Gemini LLM client
- `shared/test_types.py` — 所有測試相關 Pydantic models
- `scripts/smoke_test_gen.py` — 開發用 smoke test（正式串接後不需要）

修改既有檔案：
- `core/storage/artifacts.py` — `ensure_run_layout` 新增 `test_gen` 和 `test_gen/emitted` 子目錄
