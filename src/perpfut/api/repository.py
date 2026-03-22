"""Read-only artifact access for the operator API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import DashboardOverviewResponse, RunSummaryResponse, RunsListResponse
from ..config import AppConfig
from ..run_history import list_runs, load_run_manifest, load_run_state


class ArtifactError(RuntimeError):
    """Raised when an artifact exists but cannot be read safely."""


def get_runs_dir() -> Path:
    return AppConfig.from_env().runtime.runs_dir


def list_run_summaries(*, mode: str | None = None, limit: int = 10) -> RunsListResponse:
    items = _collect_run_summaries(get_runs_dir(), mode=mode, limit=limit)
    return RunsListResponse(items=items, count=len(items))


def build_dashboard_overview(*, mode: str, limit: int = 10) -> DashboardOverviewResponse:
    items = _collect_run_summaries(get_runs_dir(), mode=mode, limit=1)
    latest_run = items[0] if items else None
    latest_state = None
    recent_events: list[dict[str, Any]] = []
    recent_fills: list[dict[str, Any]] = []
    recent_positions: list[dict[str, Any]] = []

    if latest_run is not None:
        run_dir = get_runs_dir() / latest_run.run_id
        latest_state = load_artifact_document(run_dir.name, "state.json", required=False)
        recent_events = load_artifact_list(run_dir.name, "events.ndjson", limit=limit, required=False)
        recent_fills = load_artifact_list(run_dir.name, "fills.ndjson", limit=limit, required=False)
        recent_positions = load_artifact_list(run_dir.name, "positions.ndjson", limit=limit, required=False)

    return DashboardOverviewResponse(
        mode=mode,
        generated_at=datetime.now(timezone.utc),
        latest_run=latest_run,
        latest_state=latest_state,
        recent_events=recent_events,
        recent_fills=recent_fills,
        recent_positions=recent_positions,
    )


def load_artifact_document(run_id: str, filename: str, *, required: bool = True) -> dict[str, Any] | None:
    run_dir = _resolve_run_dir(run_id)
    path = run_dir / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    try:
        if filename == "state.json":
            return load_run_state(run_dir)
        if filename == "manifest.json":
            return load_run_manifest(run_dir)
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"invalid artifact: {path}") from exc


def load_artifact_list(
    run_id: str,
    filename: str,
    *,
    limit: int = 50,
    required: bool = True,
) -> list[dict[str, Any]]:
    run_dir = _resolve_run_dir(run_id)
    path = run_dir / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    try:
        lines = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"invalid artifact: {path}") from exc
    return list(reversed(lines))[:limit]


def _collect_run_summaries(base_dir: Path, *, mode: str | None, limit: int) -> list[RunSummaryResponse]:
    summaries: list[RunSummaryResponse] = []
    for run_dir in list_runs(base_dir):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = load_run_manifest(run_dir)
        except (OSError, json.JSONDecodeError):
            continue
        if mode is not None and manifest.get("mode") != mode:
            continue
        summaries.append(RunSummaryResponse(**_run_summary_dict(run_dir.name, manifest)))
        if len(summaries) >= limit:
            break
    return summaries


def _resolve_run_dir(run_id: str) -> Path:
    run_dir = get_runs_dir() / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    return run_dir


def _run_summary_dict(run_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": manifest.get("created_at"),
        "mode": manifest.get("mode"),
        "product_id": manifest.get("product_id"),
        "resumed_from_run_id": manifest.get("resumed_from_run_id"),
    }
