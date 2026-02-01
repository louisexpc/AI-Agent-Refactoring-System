# Repo Ingestion Module 說明

## 1) Public API 與設定

### HTTP API（FastAPI）
- POST /ingestion/runs
  - Request
    - repo_url: string
      - 目標 repo 的 Git URL 或本機路徑。若為 GitHub repo，建議使用 https URL。
    - start_prompt: string | null
      - 可選。用於描述本次 run 的目的或上下文，會記錄在 run_meta。
    - options: IngestionOptions | null
      - 可選。控制 snapshot 深度、evidence 抓取與 exec probe 等行為。
  - Response
    - run_id: string
      - 本次 ingestion run 的唯一識別碼。
- GET /ingestion/runs/{run_id}
  - Response
    - status: PENDING | RUNNING | DONE | FAILED
      - 目前 run 狀態。
    - commit_sha: string | null
      - Snapshot 取得的 commit SHA。若 snapshot 尚未完成則為 null。
    - artifacts: ArtifactRef[]
      - 已產生的 artifact 參考資訊（名稱、路徑、大小等）。
    - scopes: ScopeCandidate[]
      - Index/ScopeClassifier 產出的 scope 列表。
    - errors: ErrorSummary | null
      - 若流程失敗或 best-effort step 有錯誤，提供摘要資訊。
- GET /ingestion/runs/{run_id}/artifacts/{artifact_name}
  - 回傳指定 artifact 檔案
  - Parameters
    - artifact_name: string
      - artifact 名稱（例如 repo_index、exec_matrix）。

### IngestionOptions
- depth: int | null
  - clone 深度。null 表示使用預設值（目前實作為 1）。
- include_evidence: bool (default: true)
  - 是否抓取 GitHub evidence（issues/PR/checks）。
- max_issues: int | null
  - 最多抓取的 issues 數量。null 表示使用預設上限。
- enable_exec_probe: bool (default: true)
  - 是否執行 exec probe（install/test/coverage 的 best-effort 執行）。

### Python Public API（對內）
- IngestionService.start_run(repo_url, start_prompt, options) -> run_id
  - 建立 run 並初始化狀態為 PENDING，回傳 run_id。
- IngestionService.run_pipeline(run_id) -> None
  - 執行 ingestion pipeline（snapshot/index/exec/depgraph/data/evidence）。
- IngestionService.get_run(run_id) -> RunRecord
  - 取得 run 資料（狀態、commit_sha、scopes、artifacts）。
- IngestionService.get_artifact(run_id, name) -> Path
  - 取得指定 artifact 的檔案路徑。

## 2) Data Schema 解說

### Run / Status
- RunRecord
  - run_id: string
    - run 的唯一識別碼。
  - repo_url: string
    - 原始 repo URL 或本機路徑。
  - status: RunStatus
    - run 狀態。
  - commit_sha: string | null
    - snapshot 對應的 commit SHA。
  - start_prompt: string | null
    - 使用者提供的上下文描述。
  - created_at: datetime
    - run 建立時間。
  - updated_at: datetime
    - run 最後更新時間。
  - artifacts: ArtifactRef[]
    - 已產生的 artifacts 參考列表。
  - scopes: ScopeCandidate[]
    - scope candidates 清單。
  - errors: ErrorSummary | null
    - 錯誤摘要，若無則為 null。
- RunStatus: PENDING | RUNNING | DONE | FAILED
  - PENDING: 已建立但未開始執行
  - RUNNING: pipeline 執行中
  - DONE: pipeline 完成
  - FAILED: pipeline 失敗
- ErrorSummary: code, message, details
  - code: 錯誤代碼（簡短字串）
  - message: 錯誤摘要
  - details: 其他補充資訊（dict）

### Artifacts / Scopes / Execution
- ArtifactRef: name, path, mime, size, sha256
  - name: artifact 名稱
  - path: artifact 檔案路徑
  - mime: MIME type（可為 null）
  - size: 檔案大小（bytes，可為 null）
  - sha256: 檔案雜湊（可為 null）
- ScopeCandidate: scope_id, root_path, language, build_tool, test_tool, risk_flags
  - scope_id: scope 識別碼
  - root_path: scope 根目錄（相對路徑）
  - language: 偵測到的語言（可為 null）
  - build_tool: 主要 build 工具（可為 null）
  - test_tool: 主要 test 工具（可為 null）
  - risk_flags: 風險標記（如 templates-detected）
- ExecMatrix
  - scopes: ExecScope[]
  - per-scope 的候選命令與結果
- ExecScope
  - scope_id
  - 對應的 scope_id
  - candidates: ExecCandidate[]
  - 候選命令列表
  - results: ExecResult[]
  - 實際執行結果列表
- ExecCandidate: candidate_id, scope_id, kind, cmd, priority, tooling
  - candidate_id: 候選命令識別碼
  - scope_id: 所屬 scope
  - kind: install | test | coverage
  - cmd: 命令字串
  - priority: 執行優先順序（數字越高越優先）
  - tooling: 使用的工具（如 pip/pytest/npm）
- ExecResult: candidate_id, exit_code, duration_ms, stdout_tail, stderr_tail, artifacts
  - candidate_id: 對應的候選命令
  - exit_code: 命令的 exit code
  - duration_ms: 執行耗時（毫秒）
  - stdout_tail: stdout 尾段輸出
  - stderr_tail: stderr 尾段輸出
  - artifacts: 執行產生的 artifacts

### Snapshot / Index / DepGraph
- RepoMeta: repo_url, commit_sha, default_branch, file_count, total_bytes, created_at
  - repo_url: 原始 repo URL 或本機路徑
  - commit_sha: snapshot 固定的 commit SHA
  - default_branch: default branch 名稱（可為 null）
  - file_count: 檔案總數
  - total_bytes: 檔案總大小
  - created_at: snapshot 產生時間
- RepoIndex
  - root, file_count, total_bytes
  - root: 索引根目錄（預設為 .）
  - file_count: 索引檔案數
  - total_bytes: 索引檔案總大小
  - files: FileEntry[]
  - 檔案清單
  - indicators: string[]
  - 偵測到的 build/test/template 指標
- FileEntry: path, ext, bytes, sha1
  - path: 檔案相對路徑
  - ext: 檔案副檔名（可為 null）
  - bytes: 檔案大小
  - sha1: 檔案內容 sha1
- DepGraph
  - nodes: DepNode[]
  - 檔案/模組節點
  - edges: DepEdge[]
  - import/include/use/require 等邊
  - version, generated_at
- DepNode: node_id, path, kind, lang, ext
  - node_id: 節點識別碼（通常為路徑）
  - path: 檔案路徑
  - kind: 節點類型（預設 file）
- DepEdge: src, lang, ref_kind, dst_raw, dst_norm, dst_kind, range, confidence
  - src: 來源檔案
  - lang: 語言識別（python/js/ts/go...）
  - ref_kind: 引用類型（import/include/use/require/dynamic_import）
  - dst_raw: 原始引用字串
  - dst_norm: 正規化引用 key
  - dst_kind: internal_file | external_pkg | stdlib | relative | unknown
  - range: 來源位置範圍
  - confidence: 信心值（0~1）
  - dst_resolved_path: internal resolve 結果（可為 null）
  - symbol: from-import 的符號（可為 null）
  - is_relative: 是否為相對引用
  - extras: 語言特有資訊

### Data Assets / SQL Inventory
- DbAssetsIndex
  - assets: DbAsset[]
  - DB 相關資產清單
- DbAsset: asset_id, scope_id, kind, path
  - asset_id: 資產識別碼
  - scope_id: 所屬 scope（可為 null）
  - kind: migration | schema | seed | sql
  - path: 檔案路徑
- SqlInventory
  - items: SqlItem[]
  - 抽取到的 SQL 項目
- SqlItem: sql_id, file_path, start_line, end_line, sql_hash, sql_kind, snippet, suspected_caller
  - sql_id: SQL 識別碼
  - file_path: 檔案路徑
  - start_line: 起始行號
  - end_line: 結束行號
  - sql_hash: SQL 片段雜湊
  - sql_kind: ddl | dml | unknown
  - snippet: SQL 片段（限長）
  - suspected_caller: 推測呼叫者（可為 null）

### Evidence
- EvidenceIndex
  - issues: EvidenceRef[]
  - issues evidence 索引
  - prs: EvidenceRef[]
  - PR evidence 索引
  - checks: EvidenceRef[]
  - check runs evidence 索引
- EvidenceRef: name, path
  - name: evidence 名稱
  - path: evidence 檔案路徑

## 3) 設計架構與邊界

### Pipeline 概覽
1. Run bootstrap: 產生 run_id、寫入 run_meta.json
2. Snapshot: clone/fetch、固定 commit SHA、輸出 repo_meta 與 snapshot archive
3. Index & Scope: 產出 repo_index 與 scope_candidates
4. Exec Matrix + Probe: 生成命令候選、best-effort 執行並寫 logs/coverage
5. DepGraph: tree-sitter 解析的依賴圖 + reverse index/metrics
6. Data Assets + SQL Inventory: 索引 SQL/migration 並抽取 embedded SQL
7. Evidence: GitHub issues/PR/checks best-effort 抓取

### 主要元件與責任
- Snapshotter: 只處理 clone、commit SHA、snapshot
- RepoIndexer: 只處理檔案索引與 indicators
- ScopeClassifier: 只處理 scope 推論
- ExecMatrixBuilder: 只負責命令候選生成
- ExecProbeRunner: 只負責命令執行與 logs
- DepGraphExtractor: 依賴抽取與 reverse index/metrics
- DbAssetIndexer / SqlInventoryExtractor: DB asset 與 SQL 抽取
- GitHubEvidenceFetcher: issues/PR/checks evidence

### 邊界與限制
- Exec probe 為 best-effort，不保證成功，但會留下 logs
- Evidence 允許空集合，且 GitHub API 失敗不影響 run 完成
- SQL inventory 為 heuristic，避免誤判採保守策略
- 目前僅提供最小 MVP，不含完整 DB 儲存層與 worker queue

## 4) 使用教學

### 透過 CLI 執行一次
- 指令：
  - python runner/ingestion_main.py --repo_url <repo_url>
- 輸出：
  - artifacts/<run_id>/... 內含 snapshot/index/exec/depgraph/data/evidence 等產物

### 透過 HTTP API
1) 建立 run
- POST /ingestion/runs
- Body: { "repo_url": "...", "start_prompt": "...", "options": { ... } }

2) 查詢狀態
- GET /ingestion/runs/{run_id}

3) 下載 artifacts
- GET /ingestion/runs/{run_id}/artifacts/{artifact_name}

### Schema 產生
- scripts/generate_schemas.py 會輸出 JSON Schema 到 docs/schemas/

## 5) Artifact 目錄約定
- run_meta.json
- snapshot/repo_meta.json
- snapshot/repo.tar (或 .tar.zst)
- index/repo_index.json
- index/scope_candidates.json
- exec/exec_matrix.json
- logs/exec_probe/*.log
- coverage/coverage.json
- depgraph/dep_graph.json
- depgraph/dep_reverse_index.json
- depgraph/dep_metrics.json
- depgraph/external_deps_inventory.json
- data/db_assets_index.json
- data/sql_inventory.json
- evidence/evidence_index.json
- evidence/issues/*.json
- evidence/prs/*.json
- evidence/checks/*.json
