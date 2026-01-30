# TSMC-2026-Hackathon
## 協作規範
### 專案架構（Project Folder Template）
```
repo-root/
  api/                    # FastAPI service
  orchestrator/           # LangGraph workflow + state machine
  runner/                 # Cloud Run Job entrypoint + adapters
  eval/                   # metrics collectors, scoring, report generation
  web/                    # Vite + React + TS
  shared/                 # shared schemas (OpenAPI types, report schema)
  scripts/                # local dev scripts (bootstrap, run_once, etc.)
  docs/                   # architecture docs, ADRs
  reports/                # (optional) local output; prod goes to GCS
  .github/
    workflows/            # GitHub Actions (minimal CI)
    PULL_REQUEST_TEMPLATE.md
    ISSUE_TEMPLATE/
  pyproject.toml          # Python toolchain config (ruff/mypy/pytest)
  uv.lock                 # if you use uv (lockfile)
  .python-version         # or uv python pin
  .pre-commit-config.yaml # pre-commit hooks
  README.md
  CONTRIBUTING.md
  CODEOWNERS
```
### GitHub Repo 規範
- 禁止 direct push 到 main
- Require pull request reviews（至少 1–2 人 + Copliot）
- Require status checks to pass before merging（CI 必過）
- Block force pushes / deletion（避免歷史被改）

#### Branch 命名格式
**推薦格式（可直接寫進 CONTRIBUTING）**
- `<type>/<ticket>-<short-slug>`
- type 候選：feat|fix|chore|docs|refactor|test|infra|ci

### 開發語言版本鎖定
- Python: 3.12:
    - `.python-version` : 鎖定版本
- node: v22
-
---
### Coding Style
- `ruff format`: 維護統一 coding style
- 註解 + 參數 `typing` 設定
    ```python
    def method(args: List, arg2: Dict)-> str:
        ```
        docstrings: Recommendation : Google Python Style Guide
        ```
    ```
---
## 專案管理工具 `uv`
[Intro](https://ithelp.ithome.com.tw/m/articles/10384496)
- version: 0.9.27
### Quick Start
```sh
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# 建立環境
uv sync
# 啟用 pre-commit
uv run pre-commit install
```
#### 套件安裝與執行
- 執行 : `uv run python <your code>`
- 安裝套件 : `uv add <package you need>`
---

### Installation
```sh
# Installation
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
# 初始化虛擬環境
uv venv
# 安裝工具（進 lockfile）
uv add ruff  mypy pre-commit
# 啟用 pre-commit（你本機）
uv run pre-commit install
```
