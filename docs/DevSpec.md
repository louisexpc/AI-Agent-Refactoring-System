## 0) Repo 抓取 Module MVP 目標邊界
**輸入**

- `repo_url`
**Module MVP 必出產物（每個 run）**

1. 可重現的 repo snapshot（固定 commit SHA）
2. repo index（多語言/多子專案/多 component 的 scope candidates）
3. execution matrix（每個 scope 的 install/test/coverage 候選命令 + 偵測結果）
4. dependency graph（至少 L0：lexical import graph）
5. data/sql inventory（掃出 schema/migration/embedded SQL）
6. evidence best-effort（issues 必抓；PR/checks 可為空）
7. baseline 評估（line coverage 為核心輸出格式要能機器讀）— Python 用 `coverage.py json` 或 pytest-cov 產物即可

部署上：先用 Compute Engine VM 跑一個 API service + worker（同機即可）

---

## 1) 架構（VM single-node，Local DB + Local Artifact Store）

### 1.1 Runtime components

- **API Service（FastAPI）**：提供 `POST /runs`、`GET /runs/{id}`、`GET /runs/{id}/artifacts` 等
- **Worker（單機進程）**：接 run 任務後，順序跑 ingestion pipeline（MVP 可同步；之後再改 queue）
- **Local DB（SQLite ）**
    - SQLite：交易/索引穩、相依少
- **Artifact Store（local filesystem）**：`/var/lib/agent/artifacts/<run_id>/...`（先不做 GCS；之後再加 uploader）

### 1.2 Repo 檢索/解析工具層（generalization 的關鍵）

- **ripgrep (`rg`)**：主力做 codebase lexical search，尊重 `.gitignore`，快而穩
- **tree-sitter**：跨語言 concrete syntax tree + incremental parsing，用來抽結構（imports/defs/calls）與做範圍定位
- **Semgrep（Optional，先留 hook）**：跨語言規則掃描/guardrails，適合當第二視角（尤其 MVC 混雜 repo）

---

## 2) Pipeline（Repo 抓取模組的 implementation spec）

下面每個 step 都對應：**功能**、**輸入/輸出**、**落地檔案**、**DB 寫入**。

### Step A — Run bootstrap

**功能**

- 生成 `run_id`
- 保存 `repo_url`、時間戳、run 狀態機（PENDING/RUNNING/DONE/FAILED）

**輸入**：repo_url

**輸出**：DB: `runs` row；File System: `run_meta.json`

---

### Step B — Repo snapshot

**功能**

- clone repo（建議 `-depth 1` 起步；必要時再 fetch tags/PR refs）
- 取得 `HEAD SHA`，固定為此 run 的 source-of-truth
- 打包 snapshot（zip/tar），並排除常見 build artifacts（尊重 `.gitignore`）

**輸出**

- `artifacts/<run_id>/snapshot/repo.tar.zst`
- `repo_meta.json`（commit_sha、default_branch、file_count、bytes）

> 之後若要抓 PR diff，可用 GitHub API；snapshot 保持乾淨只針對 mainline。
>

---

### Step C — Repo indexing（多語言/多子專案/多 component）

**功能（MVP 必做）**

1. 建 `files_index`：path、ext、bytes、hash（sha1/xxhash）
2. 掃描 build/test 指標檔：
    - Python：`pyproject.toml` / `requirements.txt`
    - Node：`package.json`
    - Java：`pom.xml` / `build.gradle`
    - PHP：`composer.json`
    - templates：`views/`, `templates/`, `.erb`, `.jinja`, `.ejs` 等
3. 產出 `scope_candidates`（component classifier）
    - 每個 scope：`root_path`、language、build_tool、test_tool、risk_flags（如 “server-side rendering templates detected”）

**輸出**

- `repo_index.json`
- DB: `files`, `scopes`

---

### Step D — Execution matrix probe（install/test/coverage 候選與偵測）

**功能**

- 為每個 scope 生成候選命令（不用一次就準；要能迭代）
    - 例：Python：`python -m venv .venv && pip install -e .`、`pytest -q`、`coverage run -m pytest && coverage json -o coverage.json`
    - 例：Node：`npm ci`、`npm test`、`npm run test -- --coverage`（視 package scripts）
- 在 sandbox 執行探測（MVP 允許 “dry-run / partial”）
- 記錄：
    - exit code、stdout/stderr tail、耗時
    - 是否成功產出 coverage artifact（若有）

**輸出**

- `exec_matrix.json`
- DB: `exec_runs`, `exec_candidates`
- File System: `logs/exec_probe/*.log`

> pytest-cov 作為 pytest plugin 能自動處理 coverage 檔案合併/報告輸出，對你 line coverage 指標很方便
>

---

### Step E — Dependency graph（L0：跨語言 lexical / CST）

**功能**

- L0（MVP）：抽 “import/require/include/use” 的 edges
    - 優先：tree-sitter 在各語言的 import nodes 上取 path/symbol
    - fallback：rg regex（補 coverage）
- 產出：
    - `dep_nodes`（module/file）
    - `dep_edges`（from → to, kind=import/include）

**輸出**

- `dep_graph_l0.json`
- DB: `dep_edges`

---

### Step F — Data assets & SQL inventory（Project 3 必需）

**功能**

1. **DB asset indexing**
    - 找 `migrations/`, `schema.sql`, `.sql`, `db/`, `seed.*`
2. **Embedded SQL extraction**
    - rg 掃描 `SELECT|INSERT|UPDATE|DELETE|WITH` 等關鍵字
    - 用 tree-sitter 把命中範圍收斂到 string literal / query builder block（避免噪音）
3. 產出 `sql_inventory`
    - `sql_id`（hash）
    - location（file, start_line, end_line）
    - snippet（限制長度）
    - tags（DML/DDL/unknown）
    - suspected_caller（粗略：同檔函數名/類名）

**輸出**

- `sql_inventory.json`
- DB: `sql_items`, `db_assets`

---

### Step G — Collaboration evidence（issues 必抓；PR/checks best-effort）

**功能**

- Issues：title/body/comments（做成 evidence corpus）
- PR：若存在 → pulls/reviews/comments/files
- checks：以 PR head SHA 查 check runs（讀取）

**輸出**

- `evidence/issues/*.json`
- `evidence/prs/*.json`（可為空）
- DB: `issues`, `issue_comments`, `prs`, `pr_reviews`, `pr_comments`, `check_runs`

> 注意：你的 pipeline 必須允許 “PR=0 / checks=0” 仍正常完成（sample repo 就會發生）。
>

---

## 3) Data schema（Local DB，MVP 版）

用 **SQLite** 作為 MVP（最省事）。

### 3.1 核心表（必需）

- `runs(run_id PK, repo_url, commit_sha, status, start_prompt, created_at, updated_at)`
- `scopes(scope_id PK, run_id FK, root_path, language, build_tool, test_tool, risk_flags_json)`
- `files(file_id PK, run_id FK, path, ext, bytes, content_hash)`
- `exec_candidates(candidate_id PK, scope_id FK, kind install|test|coverage, cmd, priority)`
- `exec_runs(exec_id PK, candidate_id FK, started_at, finished_at, exit_code, stdout_tail, stderr_tail, artifacts_json)`

### 3.2 結構化分析表（Project 2/3 會用）

- `dep_edges(edge_id PK, scope_id FK, src_path, dst_ref, kind, confidence)`
- `db_assets(asset_id PK, scope_id FK, kind migration|schema|seed|config, path)`
- `sql_items(sql_id PK, scope_id FK, file_path, start_line, end_line, sql_hash, sql_kind, snippet, context_json)`

### 3.3 evidence（都存）

- `issues(issue_id PK, number, title, state, created_at, body_gcs_or_path)`
- `issue_comments(comment_id PK, issue_id FK, author, created_at, body_path)`
- `prs(pr_id PK, number, title, state, head_sha, created_at, body_path)`
- `pr_reviews(review_id PK, pr_id FK, reviewer, state, submitted_at)`
- `pr_comments(comment_id PK, pr_id FK, type issue|inline, file_path, line, author, created_at, body_path)`
- `check_runs(check_id PK, head_sha, name, conclusion, started_at, completed_at)`

---

## 4) Dev-level implementation spec（Repo Ingestion Service）

### 4.1 Repo 目錄結構（參考用，TODO與開發規範有指定目錄結構）

```
agent/
  apps/
    api/                 # FastAPI
      main.py
      routes_runs.py
    worker/              # pipeline runner
      worker.py
      pipeline.py
  core/
    config.py            # pydantic settings
    logging.py
    models/              # pydantic schemas (Run, Scope, FileIndex, ...)
    db/
      sqlite.py          # connection + migrations
      schema.sql
    storage/
      artifacts.py       # local fs layout
      blobs.py           # read/write json, logs
  ingestion/
    snapshot.py
    indexer.py
    scope_classifier.py
    exec_probe.py
    depgraph/
      extractor_rg.py
      extractor_treesitter.py
    data_assets/
      sql_inventory.py
    evidence/
      github_issues.py
      github_prs.py
      github_checks.py
  tools/
    rg.py
    treesitter.py
    semgrep.py           # optional hook
  tests/

```

### 4.2 API contract（MVP）

- `POST /runs`
    - body: `{repo_url, options{...}}`
    - response: `{run_id}`
- `GET /runs/{run_id}`
    - 回 run 狀態 + commit_sha + scopes + top artifacts
- `GET /runs/{run_id}/artifacts/{name}`
    - 下載 `repo_index.json`, `exec_matrix.json`, `sql_inventory.json`, `coverage.json` 等

（FastAPI + Pydantic 做 schema 驗證很順手；型別與序列化能力官方文件很完整 ）

### 4.3 Worker contract

- `worker.py` 監聽 DB 內 `runs.status=PENDING`（或先用 CLI `python -m worker --run_id ...`）
- 每個 step 都要：
    - 寫入 `step_status`（RUNNING/DONE/FAILED）
    - 落 artifacts（JSON/LOG）
    - 把錯誤摘要寫回 DB（便於 debug）

### 4.4 Sandbox 執行策略（VM 上最低成本）

MVP 建議做兩段式：

1. **優先 Docker sandbox**（如果 VM 允許裝 Docker）：乾淨、可重現、避免污染 host
2. **Fallback：本機 venv / nvm**（有污染風險，但 MVP 可接受）

> 這塊不建議做太複雜，指定先 VM 為主
>
