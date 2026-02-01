from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class ErrorSummary(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ArtifactRef(BaseModel):
    name: str
    path: str
    mime: str | None = None
    size: int | None = None
    sha256: str | None = None


class ScopeCandidate(BaseModel):
    scope_id: str
    root_path: str
    language: str | None = None
    build_tool: str | None = None
    test_tool: str | None = None
    risk_flags: list[str] = Field(default_factory=list)


class ExecCandidateKind(str, Enum):
    INSTALL = "install"
    TEST = "test"
    COVERAGE = "coverage"


class ExecCandidate(BaseModel):
    candidate_id: str
    scope_id: str
    kind: ExecCandidateKind
    cmd: str
    priority: int = 0
    tooling: str | None = None


class ExecResult(BaseModel):
    candidate_id: str
    exit_code: int | None = None
    duration_ms: int | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)


class ExecScope(BaseModel):
    scope_id: str
    candidates: list[ExecCandidate] = Field(default_factory=list)
    results: list[ExecResult] = Field(default_factory=list)


class ExecMatrix(BaseModel):
    scopes: list[ExecScope] = Field(default_factory=list)


class DepRange(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class DepDstKind(str, Enum):
    INTERNAL_FILE = "internal_file"
    EXTERNAL_PKG = "external_pkg"
    STDLIB = "stdlib"
    RELATIVE = "relative"
    UNKNOWN = "unknown"


class DepRefKind(str, Enum):
    IMPORT = "import"
    INCLUDE = "include"
    USE = "use"
    REQUIRE = "require"
    DYNAMIC_IMPORT = "dynamic_import"
    OTHER = "other"


class DepNode(BaseModel):
    node_id: str
    path: str
    kind: str = "file"
    lang: str | None = None
    ext: str | None = None


class DepEdge(BaseModel):
    src: str
    lang: str
    ref_kind: DepRefKind
    dst_raw: str
    dst_norm: str
    dst_kind: DepDstKind
    range: DepRange
    confidence: float
    dst_resolved_path: str | None = None
    symbol: str | None = None
    is_relative: bool | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class DepGraph(BaseModel):
    nodes: list[DepNode] = Field(default_factory=list)
    edges: list[DepEdge] = Field(default_factory=list)
    version: str = "2"
    generated_at: datetime | None = None


class DepRef(BaseModel):
    src: str
    range: DepRange


class DepReverseIndexEntry(BaseModel):
    dst: str
    refs: list[DepRef] = Field(default_factory=list)


class DepReverseIndex(BaseModel):
    items: list[DepReverseIndexEntry] = Field(default_factory=list)


class DepFileMetrics(BaseModel):
    path: str
    fan_in: int
    fan_out: int
    in_cycle: bool
    scc_id: int | None = None
    internal_ratio: float | None = None


class DepMetrics(BaseModel):
    files: list[DepFileMetrics] = Field(default_factory=list)


class ExternalDepItem(BaseModel):
    dst_norm: str
    count: int
    top_importers: list[str] = Field(default_factory=list)


class ExternalDepsInventory(BaseModel):
    items: list[ExternalDepItem] = Field(default_factory=list)


class DbAsset(BaseModel):
    asset_id: str
    scope_id: str | None = None
    kind: str
    path: str


class DbAssetsIndex(BaseModel):
    assets: list[DbAsset] = Field(default_factory=list)


class SqlItem(BaseModel):
    sql_id: str
    file_path: str
    start_line: int
    end_line: int
    sql_hash: str
    sql_kind: str
    snippet: str
    suspected_caller: str | None = None


class SqlInventory(BaseModel):
    items: list[SqlItem] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    name: str
    path: str


class EvidenceIndex(BaseModel):
    issues: list[EvidenceRef] = Field(default_factory=list)
    prs: list[EvidenceRef] = Field(default_factory=list)
    checks: list[EvidenceRef] = Field(default_factory=list)


class RepoMeta(BaseModel):
    repo_url: str
    commit_sha: str
    default_branch: str | None = None
    file_count: int
    total_bytes: int
    created_at: datetime


class FileEntry(BaseModel):
    path: str
    ext: str | None = None
    bytes: int
    sha1: str


class RepoIndex(BaseModel):
    root: str = "."
    file_count: int
    total_bytes: int
    files: list[FileEntry] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    repo_url: str
    status: RunStatus
    commit_sha: str | None = None
    start_prompt: str | None = None
    created_at: datetime
    updated_at: datetime
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    scopes: list[ScopeCandidate] = Field(default_factory=list)
    errors: ErrorSummary | None = None
