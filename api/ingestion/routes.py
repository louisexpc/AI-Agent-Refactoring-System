from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.ingestion.deps import IngestionService, get_ingestion_service
from api.ingestion.schemas import RunStatusResponse, StartRunRequest, StartRunResponse

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/runs", response_model=StartRunResponse)
def start_run(
    payload: StartRunRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> StartRunResponse:
    """啟動新的 ingestion run。

    Args:
        payload: `StartRunRequest`。
        service: DI 注入的 `IngestionService`。

    Returns:
        `StartRunResponse`。
    """
    run_id = service.start_run(
        repo_url=payload.repo_url,
        start_prompt=payload.start_prompt,
        options=payload.options.model_dump() if payload.options else None,
    )
    return StartRunResponse(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run(
    run_id: str,
    service: IngestionService = Depends(get_ingestion_service),
) -> RunStatusResponse:
    """取得 run 狀態與摘要資訊。

    Args:
        run_id: run 識別碼。
        service: DI 注入的 `IngestionService`。

    Returns:
        `RunStatusResponse`。
    """
    try:
        run = service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    return RunStatusResponse(
        status=run.status,
        commit_sha=run.commit_sha,
        artifacts=run.artifacts,
        scopes=run.scopes,
        errors=run.errors,
    )


@router.get("/runs/{run_id}/artifacts/{artifact_name}")
def get_artifact(
    run_id: str,
    artifact_name: str,
    service: IngestionService = Depends(get_ingestion_service),
) -> FileResponse:
    """下載指定 artifact 檔案。

    Args:
        run_id: run 識別碼。
        artifact_name: artifact 名稱。
        service: DI 注入的 `IngestionService`。

    Returns:
        `FileResponse`。
    """
    try:
        path = service.get_artifact(run_id, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return FileResponse(path)
