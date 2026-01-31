#   題目 AI程式碼重構
- AI智能重構程式碼
- 只可以輸入init prompt和start prompt
- 輸入 : repo網址&prompt
- 輸出 : 每輪迭代需產出重構評估報告、下輪計畫
- UI不限格式，可以是CLI、Web等等
- 平台 : GCP
### 迭代前 Pipeline
#### Repo Loader (Louis)
- Target: Clone All files + PR 報告 -> Local Cache + Indexing Database(or method)
- 對外 API : 接 `repo_url` + `prompt`(Optional)
- AST (依賴性分析)
#### Analyze & Plan (Jesse, Karl)
- Target: Agent 分析整體 repo + 重構計畫
- 提供一個 Prompt Template 引導重構方向 + 人工調整 Prompt
Recommendations:
- 分析 Module Dependency 決定改訂計畫 + Test Cases 測試
#### Generate Test (Yoyo)
- 策略：Golden Master / Snapshot Testing
    - 舊程式碼當作「標準答案 (Oracle)」：Record → Replay → Compare
    - 每輪迭代全部重跑，diff output 判斷行為是否改變

##### 設計流程
**Phase 1：識別 Entry Points（迭代前，一次性）**
- 從 Repo Loader 的 AST / dependency.json 取得模組依賴圖
- 列出所有 public class & function（entry points）
- 分層分類：
    - L1 — 程式入口（main, CLI, API endpoints）
    - L2 — 各 module 的 public API
    - L3 — 高複雜度 internal function（由 coverage 補盲區時追加）

**Phase 2：生成測試 Input（迭代前，一次性）**
- 對每個 entry point：
    - LLM 讀 function signature + docstring + 內部邏輯
    - 生成 N 組 input（含 normal / boundary / edge cases）
- 副作用處理：
    - 對有副作用的依賴（Sensor、File I/O、隨機數、時間戳）建立 mock/fake
    - 對 output 中的不確定值（timestamp、random）做 normalize

**Phase 3：錄製 Golden Snapshots（迭代前，一次性）**
- 用舊 code + 生成的 input 執行，record 所有 output
- 產出 `golden_snapshots/` 目錄，格式：
    ```
    golden_snapshots/
    ├── module_a/
    │   ├── case_normal.json      → {input: {...}, output: {...}}
    │   ├── case_boundary.json
    │   └── ...
    └── module_b/
        └── ...
    ```
- 用 coverage tool（如 coverage.py）量測覆蓋率
- 對低覆蓋 module 回到 Phase 2 追加 input

**Phase 4：Validate（每輪迭代）**
- 用同樣 input 跑重構後的 code，產出 new output
- diff(golden_snapshot, new_output) → pass/fail
- 產出 Test Report：通過率、失敗案例、coverage 變化
- 若通過率低於上一輪 → 觸發 Fallback（git revert）

##### 對外 Interface
- Input：repo path + dependency.json（from Repo Loader）+ plan.md（from Analyze & Plan）
- Output：
    - `golden_snapshots/` 目錄（迭代前產出）
    - `validate.py` 驗證腳本
    - Test Report（每輪迭代產出，給 Report 階段用）

##### 待解決問題
- 如何自動為有副作用的 dependency 產生 mock/fake
- output 不確定性的 normalize 策略（白名單 vs 正規化）
- coverage 目標門檻設定（配合整體 75% 要求）
### 迭代 Pipeline
- Package : LanGraph
Iterative Loop：Analyze → Plan → Apply → Validate → Report → Decide → 下一輪/停止

---
#### Analyze & Plan
- Input: 上輪 report + Init Plan，
- Output: 本輪 tasks（分優先序與風險）
- Metrics
    - 每輪計畫可執行率（plan→apply 成功比例）
    - 任務粒度（每輪平均改動檔案數/LOC）
---
#### Apply(修改Code)
- Tool: Git/OS/Coding Style Tool/DB API
- Input: Task from `Analyze & Plan`
- Output: Commit on Repo + Reports
---
#### Validate
- Unit Test + General Test
- Metrics:
    - Line Coverage
- Output: Test Report + Validation Score
##### Fallback(暫定要加)
- 觸發: Test Case 通過率低於上一輪(暫定) or Line Coverage 降低
---
#### Report
- 產出本輪報告 + 下輪 Start Prompt
#### Criteria & Limitation
- Can Build/Compile
- Coverage Ratio: 75%
    - Early Stopping Mechnism
- Time Limit: 15 min per iteration
- Token Limit: 50 K per interation
- Maximun Iteration : 3
