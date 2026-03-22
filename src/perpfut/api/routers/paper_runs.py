"""Paper process control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..process_manager import (
    PaperRunConflictError,
    PaperRunStateError,
    PaperRunStartError,
    PaperRunStopError,
    get_paper_process_manager,
)
from ..schemas import PaperRunRequest, PaperRunStatusResponse


router = APIRouter(tags=["paper"])


@router.get("/paper-runs/active", response_model=PaperRunStatusResponse)
def read_active_paper_run() -> PaperRunStatusResponse:
    try:
        return get_paper_process_manager().status()
    except PaperRunStateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/paper-runs", response_model=PaperRunStatusResponse, status_code=status.HTTP_201_CREATED)
def start_paper_run(request: PaperRunRequest) -> PaperRunStatusResponse:
    manager = get_paper_process_manager()
    try:
        return manager.start(request)
    except PaperRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PaperRunStartError, PaperRunStateError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/paper-runs/stop", response_model=PaperRunStatusResponse)
def stop_paper_run() -> PaperRunStatusResponse:
    try:
        return get_paper_process_manager().stop()
    except (PaperRunStopError, PaperRunStateError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
