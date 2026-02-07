from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Ingestion run 的狀態列舉。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class ErrorSummary(BaseModel):
    """流程錯誤的摘要資訊。"""

    code: str = Field(..., description="錯誤代碼（短字串，用於分類）。")
    message: str = Field(..., description="錯誤摘要訊息。")
    details: dict[str, Any] | None = Field(
        default=None, description="補充細節（結構化 dict）。"
    )


class ArtifactRef(BaseModel):
    """Artifact 的最小參考資訊。"""

    name: str = Field(..., description="Artifact 名稱（如 repo_index）。")
    path: str = Field(..., description="本地絕對路徑")
    mime: str | None = Field(default=None, description="MIME type（可為 null）。")
    size: int | None = Field(default=None, description="檔案大小（bytes）。")
    sha256: str | None = Field(default=None, description="檔案內容 SHA-256。")


class ScopeCandidate(BaseModel):
    """Repo scope 候選項（build/test 的最小範圍）。"""

    scope_id: str = Field(..., description="Scope 識別碼。")
    root_path: str = Field(..., description="Scope 根目錄（相對路徑）。")
    language: str | None = Field(default=None, description="主要語言（可為 null）。")
    build_tool: str | None = Field(
        default=None, description="主要 build 工具（可為 null）。"
    )
    test_tool: str | None = Field(
        default=None, description="主要 test 工具（可為 null）。"
    )
    risk_flags: list[str] = Field(
        default_factory=list, description="風險旗標（如 templates-detected）。"
    )


class ExecCandidateKind(str, Enum):
    """Exec candidate 的類型。"""

    INSTALL = "install"
    TEST = "test"
    COVERAGE = "coverage"


class ExecCandidate(BaseModel):
    """候選命令定義（install/test/coverage）。"""

    candidate_id: str = Field(..., description="候選命令識別碼。")
    scope_id: str = Field(..., description="所屬 scope_id。")
    kind: ExecCandidateKind = Field(..., description="候選命令種類。")
    cmd: str = Field(..., description="實際要執行的命令字串。")
    priority: int = Field(default=0, description="執行優先度（數字越大越優先）。")
    tooling: str | None = Field(
        default=None, description="使用的工具（如 pip/pytest/npm）。"
    )


class ExecResult(BaseModel):
    """候選命令的實際執行結果。"""

    candidate_id: str = Field(..., description="對應的 candidate_id。")
    exit_code: int | None = Field(default=None, description="命令 exit code。")
    duration_ms: int | None = Field(default=None, description="執行耗時（毫秒）。")
    stdout_tail: str | None = Field(default=None, description="stdout 尾段輸出。")
    stderr_tail: str | None = Field(default=None, description="stderr 尾段輸出。")
    artifacts: list[ArtifactRef] = Field(
        default_factory=list, description="執行產生的 artifact 參考。"
    )


class ExecScope(BaseModel):
    """單一 scope 的候選命令與結果集合。"""

    scope_id: str = Field(..., description="對應的 scope_id。")
    candidates: list[ExecCandidate] = Field(
        default_factory=list, description="候選命令列表。"
    )
    results: list[ExecResult] = Field(
        default_factory=list, description="實際執行結果列表。"
    )


class ExecMatrix(BaseModel):
    """跨 scope 的執行矩陣（候選命令與結果）。"""

    scopes: list[ExecScope] = Field(
        default_factory=list, description="各 scope 的候選命令與結果。"
    )


class DepRange(BaseModel):
    """來源位置範圍（line/col）。"""

    start_line: int = Field(..., description="起始行（1-based）。")
    start_col: int = Field(..., description="起始欄（0-based）。")
    end_line: int = Field(..., description="結束行（1-based）。")
    end_col: int = Field(..., description="結束欄（0-based）。")


class DepDstKind(str, Enum):
    """依賴目的地的種類。"""

    INTERNAL_FILE = "internal_file"
    EXTERNAL_PKG = "external_pkg"
    STDLIB = "stdlib"
    RELATIVE = "relative"
    UNKNOWN = "unknown"


class DepRefKind(str, Enum):
    """依賴引用的語意類型。"""

    IMPORT = "import"
    INCLUDE = "include"
    USE = "use"
    REQUIRE = "require"
    DYNAMIC_IMPORT = "dynamic_import"
    OTHER = "other"


class DepNode(BaseModel):
    """Dependency graph 的節點（通常對應檔案）。"""

    node_id: str = Field(..., description="節點識別碼（通常等於 path）。")
    path: str = Field(..., description="檔案相對路徑。")
    kind: str = Field(default="file", description="節點類型（預設為 file）。")
    lang: str | None = Field(default=None, description="語言識別（可為 null）。")
    ext: str | None = Field(default=None, description="副檔名（可為 null）。")


class DepEdge(BaseModel):
    """Dependency graph 的邊（引用關係）。"""

    src: str = Field(..., description="來源檔案相對路徑。")
    lang: str = Field(default="unknown", description="語言識別（如 python/ts）。")
    ref_kind: DepRefKind = Field(default=DepRefKind.OTHER, description="引用類型（import/include/use...）。")
    dst_raw: str = Field(default="", description="原始引用字串。")
    dst_norm: str = Field(default="", description="正規化後的引用 key。")
    dst_kind: DepDstKind = Field(
        default=DepDstKind.UNKNOWN, description="目的地分類（internal/external 等）。"
    )
    range: DepRange = Field(
        default_factory=lambda: DepRange(start_line=0, start_col=0, end_line=0, end_col=0),
        description="來源位置範圍。"
    )
    confidence: float = Field(default=0.0, description="信心值（0~1）。")
    dst_resolved_path: str | None = Field(
        default=None, description="解析到的 repo 內部路徑（可為 null）。"
    )
    symbol: str | None = Field(default=None, description="from-import 的符號名稱。")
    is_relative: bool | None = Field(default=None, description="是否為相對引用。")
    extras: dict[str, Any] = Field(
        default_factory=dict, description="語言特有資訊（如 python_level）。"
    )


class DepGraph(BaseModel):
    """整體依賴圖（節點 + 邊）。"""

    nodes: list[DepNode] = Field(default_factory=list, description="節點列表。")
    edges: list[DepEdge] = Field(default_factory=list, description="邊列表。")
    version: str = Field(default="2", description="schema 版本。")
    generated_at: datetime | None = Field(
        default=None, description="產生時間（可為 null）。"
    )


class DepRef(BaseModel):
    """反向索引中的引用資訊。"""

    src: str = Field(..., description="引用來源檔案路徑。")
    range: DepRange = Field(..., description="來源位置範圍。")


class DepReverseIndexEntry(BaseModel):
    """反向索引單筆項目（被引用目標）。"""

    dst: str = Field(..., description="被引用的 key（resolved path 或 dst_norm）。")
    refs: list[DepRef] = Field(default_factory=list, description="引用來源清單。")


class DepReverseIndex(BaseModel):
    """反向索引（被引用目標 → 來源）。"""

    items: list[DepReverseIndexEntry] = Field(
        default_factory=list, description="反向索引項目列表。"
    )


class DepFileMetrics(BaseModel):
    """單檔案依賴指標（fan-in/out 等）。"""

    path: str = Field(..., description="檔案相對路徑。")
    fan_in: int = Field(..., description="被其他檔案引用次數。")
    fan_out: int = Field(..., description="引用其他檔案次數。")
    in_cycle: bool = Field(..., description="是否在循環相依中。")
    scc_id: int | None = Field(default=None, description="SCC 編號（可為 null）。")
    internal_ratio: float | None = Field(
        default=None, description="internal 依賴比例（0~1，可為 null）。"
    )


class DepMetrics(BaseModel):
    """依賴圖衍生指標集合。"""

    files: list[DepFileMetrics] = Field(
        default_factory=list, description="每個檔案的指標列表。"
    )


class ExternalDepItem(BaseModel):
    """單一外部依賴統計項目。"""

    dst_norm: str = Field(..., description="外部依賴的正規化 key。")
    count: int = Field(..., description="被引用次數。")
    top_importers: list[str] = Field(
        default_factory=list, description="引用最多的來源檔案清單。"
    )


class ExternalDepsInventory(BaseModel):
    """外部依賴盤點清單。"""

    items: list[ExternalDepItem] = Field(
        default_factory=list, description="外部依賴統計項目列表。"
    )


class DbAsset(BaseModel):
    """資料庫資產（migration/schema/seed/sql）。"""

    asset_id: str = Field(..., description="資產識別碼。")
    scope_id: str | None = Field(default=None, description="所屬 scope（可為 null）。")
    kind: str = Field(..., description="資產種類（migration/schema/seed/sql）。")
    path: str = Field(..., description="檔案相對路徑。")


class DbAssetsIndex(BaseModel):
    """資料庫資產索引。"""

    assets: list[DbAsset] = Field(default_factory=list, description="資產列表。")


class SqlItem(BaseModel):
    """SQL 片段抽取結果。"""

    sql_id: str = Field(..., description="SQL 識別碼。")
    file_path: str = Field(..., description="來源檔案路徑。")
    start_line: int = Field(..., description="起始行號（1-based）。")
    end_line: int = Field(..., description="結束行號（1-based）。")
    sql_hash: str = Field(..., description="SQL 片段雜湊。")
    sql_kind: str = Field(..., description="SQL 類型（ddl/dml/unknown）。")
    snippet: str = Field(..., description="SQL 片段（限長）。")
    suspected_caller: str | None = Field(
        default=None, description="推測呼叫者（可為 null）。"
    )


class SqlInventory(BaseModel):
    """SQL 盤點清單。"""

    items: list[SqlItem] = Field(default_factory=list, description="SQL 片段列表。")


class EvidenceRef(BaseModel):
    """Evidence 參考項目（檔案路徑）。"""

    name: str = Field(..., description="Evidence 名稱（如 issue_123）。")
    path: str = Field(..., description="Evidence 檔案路徑。")


class EvidenceIndex(BaseModel):
    """Evidence 索引（issues/prs/checks）。"""

    issues: list[EvidenceRef] = Field(
        default_factory=list, description="Issue evidence 清單。"
    )
    prs: list[EvidenceRef] = Field(
        default_factory=list, description="PR evidence 清單。"
    )
    checks: list[EvidenceRef] = Field(
        default_factory=list, description="CI checks evidence 清單。"
    )


class RepoMeta(BaseModel):
    """Snapshot 後的 repo 基本資訊。"""

    repo_url: str = Field(..., description="原始 repo URL 或本機路徑。")
    commit_sha: str = Field(..., description="snapshot 固定的 commit SHA。")
    default_branch: str | None = Field(default=None, description="default branch。")
    file_count: int = Field(..., description="檔案總數。")
    total_bytes: int = Field(..., description="檔案總大小（bytes）。")
    created_at: datetime = Field(..., description="snapshot 建立時間。")


class FileEntry(BaseModel):
    """Repo 索引中的單一檔案記錄。"""

    path: str = Field(..., description="檔案相對路徑。")
    ext: str | None = Field(default=None, description="副檔名（可為 null）。")
    bytes: int = Field(..., description="檔案大小（bytes）。")
    sha1: str = Field(..., description="檔案內容 SHA-1。")


class RepoIndex(BaseModel):
    """Repo 索引（檔案清單與指標）。"""

    root: str = Field(default=".", description="索引根目錄。")
    file_count: int = Field(..., description="索引檔案數。")
    total_bytes: int = Field(..., description="索引檔案總大小（bytes）。")
    files: list[FileEntry] = Field(default_factory=list, description="檔案清單。")
    indicators: list[str] = Field(
        default_factory=list, description="偵測到的 build/test/template 指標。"
    )


class RunRecord(BaseModel):
    """Ingestion run 的主紀錄。"""

    run_id: str = Field(..., description="run 識別碼。")
    repo_url: str = Field(..., description="repo URL 或本機路徑。")
    status: RunStatus = Field(..., description="run 狀態。")
    commit_sha: str | None = Field(default=None, description="snapshot commit SHA。")
    start_prompt: str | None = Field(default=None, description="啟動提示字串。")
    created_at: datetime = Field(..., description="建立時間。")
    updated_at: datetime = Field(..., description="最後更新時間。")
    artifacts: dict[str, list[ArtifactRef]] = Field(
        default_factory=dict, description="已產生的 artifacts 參考。"
    )
    scopes: list[ScopeCandidate] = Field(
        default_factory=list, description="scope candidates 列表。"
    )
    errors: ErrorSummary | None = Field(default=None, description="錯誤摘要。")
