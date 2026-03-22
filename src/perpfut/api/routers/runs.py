"""Run artifact endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..repository import ArtifactError, list_run_summaries, load_artifact_document, load_artifact_list
from ..schemas import ArtifactDocumentResponse, ArtifactListResponse, RunsListResponse


router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=RunsListResponse)
def read_runs(
    mode: Literal["paper", "live"] | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=200),
) -> RunsListResponse:
    return list_run_summaries(mode=mode, limit=limit)


@router.get("/runs/{run_id}/manifest", response_model=ArtifactDocumentResponse)
def read_run_manifest(run_id: str) -> ArtifactDocumentResponse:
    return ArtifactDocumentResponse(run_id=run_id, data=_load_document(run_id, "manifest.json"))


@router.get("/runs/{run_id}/state", response_model=ArtifactDocumentResponse)
def read_run_state(run_id: str) -> ArtifactDocumentResponse:
    return ArtifactDocumentResponse(run_id=run_id, data=_load_document(run_id, "state.json"))


@router.get("/runs/{run_id}/events", response_model=ArtifactListResponse)
def read_run_events(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> ArtifactListResponse:
    return _build_list_response(run_id, "events.ndjson", limit=limit)


@router.get("/runs/{run_id}/fills", response_model=ArtifactListResponse)
def read_run_fills(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> ArtifactListResponse:
    return _build_list_response(run_id, "fills.ndjson", limit=limit)


@router.get("/runs/{run_id}/positions", response_model=ArtifactListResponse)
def read_run_positions(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> ArtifactListResponse:
    return _build_list_response(run_id, "positions.ndjson", limit=limit)


def _load_document(run_id: str, filename: str) -> dict:
    try:
        data = load_artifact_document(run_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    assert data is not None
    return data


def _build_list_response(run_id: str, filename: str, *, limit: int) -> ArtifactListResponse:
    try:
        items = load_artifact_list(run_id, filename, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ArtifactListResponse(run_id=run_id, items=items, count=len(items))
