from __future__ import annotations

from pydantic import BaseModel, Field

from shared.ingestion_types import ArtifactRef, ErrorSummary, RunStatus, ScopeCandidate


class IngestionOptions(BaseModel):
    """Ingestion 的可選參數。"""

    depth: int | None = None
    include_evidence: bool = True
    max_issues: int | None = None
    enable_exec_probe: bool = True


class StartRunRequest(BaseModel):
    """啟動 run 的 request DTO。"""

    repo_url: str
    start_prompt: str | None = None
    save_path: str = "/workspace"
    options: IngestionOptions | None = None


class StartRunResponse(BaseModel):
    """啟動 run 的 response DTO。"""

    run_id: str
    run_dir: str = Field(..., description="clone repo 分析本地絕對路徑dir")


class RunStatusResponse(BaseModel):
    """run 狀態查詢的 response DTO。
    artifacts 欄位目前只提供 :
        - "depgraph": 依賴關係圖產物
        - "exec_matrix": 執行矩陣產物
        - "index": Repo 索引產物
    """

    status: RunStatus
    commit_sha: str | None = None
    artifacts: dict[str, list[ArtifactRef]] = Field(default_factory=dict)
    scopes: list[ScopeCandidate] = Field(default_factory=list)
    errors: ErrorSummary | None = None
