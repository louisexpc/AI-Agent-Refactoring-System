from __future__ import annotations

from pydantic import BaseModel, Field

from shared.ingestion_types import ArtifactRef, ErrorSummary, RunStatus, ScopeCandidate


class IngestionOptions(BaseModel):
    depth: int | None = None
    include_evidence: bool = True
    max_issues: int | None = None
    enable_exec_probe: bool = True


class StartRunRequest(BaseModel):
    repo_url: str
    start_prompt: str | None = None
    options: IngestionOptions | None = None


class StartRunResponse(BaseModel):
    run_id: str


class RunStatusResponse(BaseModel):
    status: RunStatus
    commit_sha: str | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    scopes: list[ScopeCandidate] = Field(default_factory=list)
    errors: ErrorSummary | None = None
