"""Progress updates for background backtest jobs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENV_ACTIVE_METADATA_PATH = "PERPFUT_BACKTEST_ACTIVE_METADATA_PATH"
ENV_JOB_METADATA_PATH = "PERPFUT_BACKTEST_JOB_METADATA_PATH"


@dataclass(frozen=True, slots=True)
class BacktestProgressUpdate:
    phase: str
    phase_message: str | None = None
    total_runs: int | None = None
    completed_runs: int | None = None
    error: str | None = None


class BacktestProgressReporter:
    def __init__(self, *, metadata_paths: tuple[Path, ...]):
        self.metadata_paths = metadata_paths

    @classmethod
    def from_env(cls) -> "BacktestProgressReporter | None":
        metadata_paths = tuple(
            Path(path)
            for path in (
                os.environ.get(ENV_ACTIVE_METADATA_PATH),
                os.environ.get(ENV_JOB_METADATA_PATH),
            )
            if path
        )
        if not metadata_paths:
            return None
        return cls(metadata_paths=metadata_paths)

    def emit(self, update: BacktestProgressUpdate) -> None:
        heartbeat = datetime.now(timezone.utc).isoformat()
        for path in self.metadata_paths:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            payload["phase"] = update.phase
            payload["phase_message"] = update.phase_message
            payload["last_heartbeat_at"] = heartbeat
            if update.total_runs is not None:
                payload["total_runs"] = update.total_runs
            if update.completed_runs is not None:
                payload["completed_runs"] = update.completed_runs
            if update.error is not None:
                payload["error"] = update.error
            _write_json(path, payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
