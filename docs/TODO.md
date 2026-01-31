## 1) Public API 介面規劃（Repo Ingestion Module）

目前的 repo 是共用大 repo（含 `api/`, `runner/`, `shared/`…），但本回合只定義「Repo 抓取模組」的公開邊界：**一個可被呼叫的 ingestion service** + **一個可重入的 pipeline runner**。

### 1.1 HTTP API（FastAPI）— 對外/對上層（最小必需）

> 放在 api/，遵守你們 README 的 FastAPI service 位置 README；也符合 FastAPI 典型的 path operation 與 dependency injection 使用方式
>

**Run 管理**

- `POST /ingestion/runs`
    - Request
        - `repo_url: str`
        - `options?: IngestionOptions`（可選：`depth`, `include_evidence`, `max_issues`, `enable_exec_probe`…）
    - Response
        - `run_id: str`
- `GET /ingestion/runs/{run_id}`
    - Response
        - `status: PENDING|RUNNING|DONE|FAILED`
        - `commit_sha: str | null`
        - `artifacts: {name: uri_or_path}[]`
        - `scopes: ScopeSummary[]`
        - `errors?: ErrorSummary`
- `GET /ingestion/runs/{run_id}/artifacts/{artifact_name}`
    - 直接回傳 artifact 檔案（JSON/zip/log）

**為什麼只到這裡就夠**

- 你的 ingestion 是「離線產物生成器」，上層框架只要能 **啟動一次 run**、**查狀態**、**拉 artifacts** 就可串接。

---

### 1.2 Python Public API（對內/對 runner）

> 目標：API 與 pipeline 解耦，讓未來可在 VM 直接跑 CLI/Job，不一定依賴 HTTP。
>
- `IngestionService.start_run(repo_url, start_prompt, options) -> RunId`
- `IngestionService.run_pipeline(run_id) -> None`
- `IngestionService.get_run(run_id) -> RunRecord`
- `IngestionService.get_artifact(run_id, name) -> Path`

> 註：FastAPI route 只呼叫 IngestionService，不要直接碰 git/rg/tree-sitter。
>

---

## 2) Repo 抓取模組的專案架構（嚴格依 README.md 模板）

你上傳的模板是 repo-root 的固定骨架
README。我們不改動骨架，只在既有資料夾內放「ingestion 模組」的程式碼位置。

### 2.1 目錄對應（不新增頂層資料夾）

依模板，建議這樣放：

```perl
    # FastAPI service（保留）
    ingestion/# 本模組對外 API（routes + schemas）
      routes.py
      schemas.py
      deps.py# FastAPI DI（可選）
    main.py

  runner/# 本模組可直接跑的 entrypoint（VM/Job）
    ingestion_main.py# CLI: run once / resume
    adapters/# (可選) 未來接 Cloud Run Job 的封裝

  shared/# shared schemas（跨模組共用）
    ingestion_types.py# Run/Artifact/Scope/ExecMatrix 的共用 schema

  scripts/# local dev scripts
    ingestion_run_once.sh

  docs/# ingestion 模組設計/ADR
    ingestion_spec.md
    adr/ADR-0001-ingestion-artifacts.md

  pyproject.toml# ruff/mypy/pytest（模板要求）
  uv.lock# uv（模板要求）
  .python-version # （模板要求）
  .pre-commit-config.yaml  #（模板要求）

```

README（你 README 已明確）

- Python 版本：3.12（`.python-version`）
- Node 版本：v22（之後前端用；本模組可先不動）
- 格式化：`ruff format
- 型別/註解：typing + docstring
- 套件

---

## 3) 依 DevSpec.md 的順序是「**先定義 contract → 再落 pipeline** artifacts。

### Phase 0 — Contracts First（先定義 Public API + schemas）

1. `shared/ingestion_types.py`
    - `RunRecord`, `RunStatus`
    - `ArtifactRef {name, path, mime, size, sha256}`
    - `ScopeCandidate {scope_id, root_path, language, build_tool, test_tool, risk_flags}`
    - `ExecCandidate / ExecResult`
2. `api/ingestion/schemas.py`（HTTP request/response DTO，盡量重用 shared types）
3. `api/ingestion/routes.py`（先 stub：先回 run_id、狀態假資料也行）

> 這步完成後，runner/pipeline 才能「照 schema 產物輸出」。
>

---

### Phase 1 — Storage & Run lifecycle（SOLID：把狀態與 IO 隔離）

1. `runner/ingestion_main.py`（CLI skeleton：`run_once --repo_url ...`）
2. `runner` 內建立最小的 infra（不新增頂層）
    - `RunRepository`（SQLite或純 JSON index 都可；MVP 開發階段 DB 先簡單/甚至 local）
    - `ArtifactStore`（local filesystem layout + atomic write）
    - 先把 `runs` 的狀態流轉做完：PENDING→RUNNING→DONE/FAILED

---

### Phase 2 — Snapshot（抓 repo + 固定 SHA）

1. `Snapshotter`
    - clone / fetch / resolve default branch
    - 固定 `commit_sha`
    - 打包 snapshot
2. 產出 artifacts：
    - `repo_meta.json`
    - `snapshot/repo.tar(.zst)`

        （後續所有 step 都只讀 snapshot 工作目錄）


---

### Phase 3 — Index & Scope candidates（泛化核心）

1. `RepoIndexer`
    - 檔案樹、語言分佈、關鍵 build 檔偵測
2. `ScopeClassifier`
    - 生成 `scope_candidates.json`（多子專案/多 component）
3. artifacts：
- `repo_index.json`
- `scope_candidates.json`

---

### Phase 4 — Execution Matrix Probe（install/test/coverage 候選）

1. `ExecMatrixBuilder`
- 依 scope 的 build files 推測命令候選
1. `ExecProbeRunner`
- best-effort 執行：記錄 exit code、log tail
- coverage：Python 優先 `coverage json`（產 JSON 報告）
1. artifacts：
- `exec_matrix.json`
- `logs/exec_probe/*.log`
- （若成功）`coverage/coverage.json`

---

### Phase 5 — Dependency Graph L0（跨語言穩定）

1. `DepGraphExtractor`
- primary：tree-sitter（增量 parsing + concrete syntax tree）
- fallback：ripgrep（尊重 .gitignore、快）
1. artifacts：
- `dep_graph_l0.json`

---

### Phase 6 — Data Assets & SQL Inventory（Project 3 必備）

1. `DbAssetIndexer`
- migrations/schema/*.sql 索引
1. `SqlInventoryExtractor`
- rg 先撈候選，再用 tree-sitter/規則縮範圍（避免噪音）
1. artifacts：
- `db_assets_index.json`
- `sql_inventory.json`

---

### Phase 7 — Evidence（issues 必抓；PR/checks best-effort）

1. `GitHubEvidenceFetcher`
- issues + comments（必做）
- PR/reviews/checks（可選、允許空）
1. artifacts：
- `evidence/issues/*.json`
- `evidence/prs/*.json`（可空）

---

## SOLID 對應：每個核心類別的責任邊界

- **Single Responsibility**
    - `Snapshotter` 只負責取得固定 SHA 與 snapshot
    - `RepoIndexer` 只負責 file tree/index
    - `ScopeClassifier` 只負責 scope candidate 生成
    - `ExecProbeRunner` 只負責跑命令並記錄結果
- **Open/Closed**
    - `DepGraphExtractor` 採策略模式：`TreeSitterExtractor` / `RgExtractor`
    - `ExecMatrixBuilder` 可按語言擴充 plugin（python/node/java/php…）
- **Liskov / Interface Segregation**
    - 對外只暴露 `IngestionService`；內部各 step 實作 `PipelineStep` 介面
- **Dependency Inversion**
    - `Pipeline` 依賴 `RunRepository` / `ArtifactStore` 抽象介面，不依賴具體 SQLite/FS

---
# 交付 ticket 清單
## Phase 0 — Contracts / Schemas（先把「形狀」定死）

### T0.1 定義 shared ingestion schemas（Pydantic models）

**交付**

- `shared/ingestion_types.py`：`RunRecord`, `ScopeCandidate`, `ArtifactRef`, `ExecMatrix`, `DepGraphL0`, `SqlInventory`, `EvidenceIndex` 等 model
- `docs/ingestion_spec.md`：列出每個 artifact 對應的 model 名稱（不用寫長文，列 mapping 即可）

**驗收**

- 能從 Pydantic 生成 JSON Schema（`model_json_schema()`）且輸出到 `docs/schemas/*.json`（或至少可在 CI/本機執行生成）。
- 後續所有 artifact JSON 都要用 `model_validate_json()` / `TypeAdapter.validate_json()` 走「JSON mode」驗證，不允許只用 `json.loads` 草率過關。

---

### T0.2 FastAPI DTO（request/response）與 routes 骨架

**交付**

- `api/ingestion/schemas.py`：HTTP request/response model（重用 shared types）
- `api/ingestion/routes.py`：先 stub `POST /ingestion/runs`, `GET /ingestion/runs/{id}`, `GET /ingestion/runs/{id}/artifacts/{name}`

**驗收**

- FastAPI 的 `response_model` 生效：回傳資料不符合 schema 時會被擋/被過濾（基本防線）。
- `repo-root/api/` 位置與模板一致。 README

---

## Phase 1 — Run lifecycle + Local Storage（先能「跑一次、留下所有檔」）

### T1.1 RunRepository（SQLite）+ ArtifactStore（local FS）最小實作

**交付**

- `runner/ingestion_main.py`：CLI 可 `run_:contentReference[oaicite:5]{index=5}`shared `內：`RunStatus` 狀態機（PENDING/RUNNING/DONE/FAILED）
- `artifacts/<run_id>/run_meta.json`（run 的最小 metadata）

**驗收**

- `GET /ingestion/runs/{id}` 可看到狀態流轉（即使尚未 clone）。
- `run_meta.json` 可用 `RunRecord.model_validate_json()` 通過。

---

### T1.2 統一 artifact layout（固定路徑約定）

**交付**

- `core/storage/artifacts.py`（或相對應位置）：定義
    - `snapshot/`, `index/`, `exec/`, `depgraph/`, `data/`, `evidence/`, `logs/`
- `docs/ingestion_spec.md` 補上「artifact name → 實體路徑」表

**驗收**

- 任一 run 必定產生固定目錄骨架（即使後續 step fail 也能留下 log/partial artifacts）。

---

## Phase 2 — Snapshot（repo clone + 固定 SHA + 打包）

### T2.1 Snapshotter（clone/checkout/sha）

**交付**

- `artifacts/<run_id>/snapshot/repo/`（工作目錄或解壓區）
- `artifacts/<run_id>/snapshot/repo_meta.json`（commit_sha/default_branch/clone_time/file_count…）
- （可選）`snapshot/repo.tar(.zst)`：打包備份

**驗收**

- `repo_meta.json` 通過 schema validation（Pydantic）。
- commit SHA 一旦確定，後續所有 step 都只讀這個 snapshot（可重現性）。

---

## Phase 3 — Repo Index + Scope Candidates（泛化核心）

### T3.1 RepoIndexer（file index + language hints）

**交付**

- `artifacts/<run_id>/index/repo_index.json`
    - files：path/ext/bytes/hash（hash 可先 sha1）
    - top-level indicators：pyproject/package.json/pom/build.gradle/templates 等

**驗收**

- `repo_index.json` 必須通過 schema validation。
- 對大 repo 掃描時尊重 `.gitignore`（後續用 rg 時同樣）。

---

### T3.2 ScopeClassifier（component/scope candidates）

**交付**

- `artifacts/<run_id>/index/scope_candidates.json`
    - 每個 scope：root_path、language、build_tool、test_tool、risk_flags（如 SSR templates detected）

**驗收**

- `scope_candidates.json` 通過 schema validation。
- 至少能產出 1 個 scope（即便偵測不到，也要有 fallback scope=repo-root）。

---

## Phase 4 — Exec Matrix（install/test/coverage 候選 + best-effort probe）

### T4.1 ExecMatrixBuilder（命令候選生成）

**交付**

- `artifacts/<run_id>/exec/exec_matrix.json`
    - per-scope: install/test/coverage 候選 commands（含 priority、tooling）

**驗收**

- `exec_matrix.json` 通過 schema validation。
- 命令候選至少要能覆蓋 Python / Node 兩類（其他先留 stub 欄位）。

---

### T4.2 ExecProbeRunner（嘗試執行 + logs）

**交付**

- `artifacts/<run_id>/logs/exec_probe/*.log`
- `artifacts/<run_id>/exec/exec_probe_results.json`（或寫回 exec_matrix 的 results 欄位）

**驗收**

- probe 不要求成功，但必須：
    - 每個 scope 至少嘗試 1 組 test 或 coverage
    - log 必存在（stdout/stderr tail）
- 若 scope 為 Python 且能跑 tests，優先產 coverage JSON：Coverage.py 支援 `json` report（`coverage json`）。

---

## Phase 5 — Dependency Graph L0（tree-sitter + rg fallback）

### T5.1 DepGraphExtractor（L0）

**交付**

- `artifacts/<run_id>/depgraph/dep_graph_l0.json`
    - nodes：file/module
    - edges：import/include/require（confidence）

**驗收**

- `dep_graph_l0.json` 通過 schema validation。
- tree-sitter 作為 primary：可建 concrete syntax tree、支援 incremental parsing；失敗才 fallback rg。
- rg fallback 必尊重 gitignore，避免掃到 vendor/build。

---

## Phase 6 — Data Assets + SQL Inventory（Project 3 必備）

### T6.1 DbAssetIndexer（schema/migrations/sql files）

**交付**

- `artifacts/<run_id>/data/db_assets_index.json`

**驗收**

- 通過 schema validation。
- 至少能列出：`.sql`、`migrations/`、`schema.*`、常見 seed 路徑（找不到也要輸出空陣列而非 fail）。

---

### T6.2 SqlInventoryExtractor（embedded SQL + hash）

**交付**

- `artifacts/<run_id>/data/sql_inventory.json`
    - sql_id/hash、file_path、line range、snippet（限長）、sql_kind（DML/DDL/unknown）

**驗收**

- 通過 schema validation。
- 以 rg 先撈 `SELECT/INSERT/UPDATE/DELETE/WITH` 候選，再用 tree-sitter/規則收斂到 string literal/query block（至少要實作「避免整檔誤判」的最小邏輯）。

---

## Phase 7 — Evidence（issues 必抓；PR/checks best-effort）

### T7.1 GitHub Issues fetch（必做）

**交付**

- `artifacts/<run_id>/evidence/issues/*.json`
- `artifacts/<run_id>/evidence/evidence_index.json`（總索引）

**驗收**

- 即使沒有 issues 也要成功完成（輸出空集合）。
- 依 GitHub REST 規格抓 issue + comments（最少 title/body/comments）。

---

### T7.2 PR / Reviews / Check-runs（best-effort）

**交付**

- `artifacts/<run_id>/evidence/prs/*.json`（可空）
- `artifacts/<run_id>/evidence/checks/*.json`（可空）

**驗收**

- PR 相關 endpoints（pulls / reviews / review comments）依 GitHub REST 文件實作；取不到（權限/不存在）不得讓整個 run fail。
- checks：讀取 check runs；「建立 check run」需要 GitHub App，但你們 ingestion 只讀即可。

---

## 全域驗收門檻（每個 Phase 都適用）

1. **Artifact existence**：每張 ticket 指定的檔案路徑必須存在（空集合也可，但檔案要存在）。
2. **Schema validation**：所有 JSON artifacts 必須能被對應 Pydantic model 以 `model_validate_json()` 驗過。
3. **Fail-safe**：best-effort 模組（exec probe、evidence PR/checks）失敗不得中止整個 run；只允許把該 step 標記為 PARTIAL/FAILED 並留下 logs。
4. **Template compliance**：不新增頂層資料夾，落在模板定義的 `api/runner/shared/scripts/docs` 等結構中。

---
