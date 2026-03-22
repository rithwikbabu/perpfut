"""Helpers for inspecting and resuming from local run artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def list_runs(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted(
        [path for path in base_dir.iterdir() if path.is_dir()],
        reverse=True,
    )


def load_run_manifest(run_dir: Path) -> dict[str, Any]:
    return _load_json(run_dir / "manifest.json")


def load_run_state(run_dir: Path) -> dict[str, Any]:
    return _load_json(run_dir / "state.json")


def find_latest_run(
    base_dir: Path,
    *,
    mode: str | None = None,
    product_id: str | None = None,
    require_state: bool = False,
) -> Path | None:
    for run_dir in list_runs(base_dir):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        if require_state and not _has_readable_state(run_dir):
            continue
        try:
            manifest = load_run_manifest(run_dir)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        if mode is not None and manifest.get("mode") != mode:
            continue
        if product_id is not None and manifest.get("product_id") != product_id:
            continue
        return run_dir
    return None


def summarize_runs(base_dir: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    summaries = []
    for run_dir in list_runs(base_dir)[:limit]:
        manifest = {}
        if (run_dir / "manifest.json").exists():
            try:
                loaded = load_run_manifest(run_dir)
            except (OSError, json.JSONDecodeError):
                loaded = {}
            manifest = loaded if isinstance(loaded, dict) else {}
        summaries.append(
            {
                "run_id": run_dir.name,
                "created_at": manifest.get("created_at"),
                "mode": manifest.get("mode"),
                "product_id": manifest.get("product_id"),
                "resumed_from_run_id": manifest.get("resumed_from_run_id"),
            }
        )
    return summaries


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_readable_state(run_dir: Path) -> bool:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        return False
    try:
        payload = _load_json(state_path)
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict)
