"""Backtest API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..backtest_manager import (
    BacktestJobConflictError,
    BacktestJobStartError,
    BacktestJobStateError,
    get_backtest_job_manager,
)
from ..repository import (
    ArtifactError,
    list_backtest_run_summaries,
    list_backtest_suite_summaries,
    load_artifact_list,
    load_backtest_run_detail,
    load_backtest_suite_detail,
    load_run_analysis,
)
from ..schemas import (
    ArtifactListResponse,
    BacktestJobStatusResponse,
    BacktestRunDetailResponse,
    BacktestRunRequest,
    BacktestsListResponse,
    BacktestSuiteDetailResponse,
    BacktestSuitesListResponse,
    RunAnalysisResponse,
)


router = APIRouter(tags=["backtests"])


@router.get("/backtests", response_model=BacktestsListResponse)
def read_backtests(limit: int = Query(default=10, ge=1, le=200)) -> BacktestsListResponse:
    manager = get_backtest_job_manager()
    try:
        active_job = manager.status()
        latest_job = next(iter(manager.list_jobs(limit=1)), None)
    except BacktestJobStateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        items = list_backtest_run_summaries(limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid backtest artifacts") from exc
    return BacktestsListResponse(items=items, count=len(items), active_job=active_job, latest_job=latest_job)


@router.post("/backtests", response_model=BacktestJobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def start_backtest_job(request: BacktestRunRequest) -> BacktestJobStatusResponse:
    manager = get_backtest_job_manager()
    try:
        return manager.start(request)
    except BacktestJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (BacktestJobStartError, BacktestJobStateError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtests/{run_id}", response_model=BacktestRunDetailResponse)
def read_backtest_run(run_id: str) -> BacktestRunDetailResponse:
    try:
        return load_backtest_run_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtests/{run_id}/analysis", response_model=RunAnalysisResponse)
def read_backtest_analysis(run_id: str) -> RunAnalysisResponse:
    try:
        analysis = load_run_analysis(f"backtests/runs/{run_id}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="analysis inputs not found") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    assert analysis is not None
    return analysis


@router.get("/backtests/{run_id}/events", response_model=ArtifactListResponse)
def read_backtest_events(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "events.ndjson", limit=limit)


@router.get("/backtests/{run_id}/positions", response_model=ArtifactListResponse)
def read_backtest_positions(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "positions.ndjson", limit=limit)


@router.get("/backtests/{run_id}/fills", response_model=ArtifactListResponse)
def read_backtest_fills(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "fills.ndjson", limit=limit)


@router.get("/backtest-suites", response_model=BacktestSuitesListResponse)
def read_backtest_suites(limit: int = Query(default=10, ge=1, le=200)) -> BacktestSuitesListResponse:
    manager = get_backtest_job_manager()
    try:
        active_job = manager.status()
        latest_job = next(iter(manager.list_jobs(limit=1)), None)
    except BacktestJobStateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        items = list_backtest_suite_summaries(limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid backtest suite artifacts") from exc
    return BacktestSuitesListResponse(items=items, count=len(items), active_job=active_job, latest_job=latest_job)


@router.get("/backtest-suites/{suite_id}", response_model=BacktestSuiteDetailResponse)
def read_backtest_suite_detail(suite_id: str) -> BacktestSuiteDetailResponse:
    try:
        return load_backtest_suite_detail(suite_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _build_backtest_list_response(run_id: str, filename: str, *, limit: int) -> ArtifactListResponse:
    try:
        items = load_artifact_list(f"backtests/runs/{run_id}", filename, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ArtifactListResponse(run_id=run_id, items=items, count=len(items))
