"""Structured logging and artifact writing."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .config import AppConfig
from .domain import CycleResult, PositionState


LOGGER = logging.getLogger("perpfut")


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _resolve_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except Exception:
        return "nogit"
    return result.stdout.strip() or "nogit"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


class ArtifactStore:
    """Append-only run artifacts for debugging and replay."""

    def __init__(self, run_dir: Path, *, resumed_from_run_id: str | None = None):
        self.run_dir = run_dir
        self.manifest_path = run_dir / "manifest.json"
        self.config_path = run_dir / "config.json"
        self.events_path = run_dir / "events.ndjson"
        self.fills_path = run_dir / "fills.ndjson"
        self.positions_path = run_dir / "positions.ndjson"
        self.state_path = run_dir / "state.json"
        self.run_id = run_dir.name
        self.resumed_from_run_id = resumed_from_run_id

    @classmethod
    def create(cls, base_dir: Path, *, resumed_from_run_id: str | None = None) -> "ArtifactStore":
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = base_dir / f"{timestamp}_{_resolve_git_sha()}"
        run_dir.mkdir(parents=True, exist_ok=False)
        return cls(run_dir, resumed_from_run_id=resumed_from_run_id)

    def write_metadata(
        self,
        config: AppConfig,
        *,
        extra_manifest: dict[str, Any] | None = None,
    ) -> None:
        manifest = {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc),
            "mode": config.runtime.mode,
            "product_id": config.runtime.product_id,
            "strategy_id": config.strategy.strategy_id,
            "git_sha": _resolve_git_sha(),
            "resumed_from_run_id": self.resumed_from_run_id,
        }
        if extra_manifest:
            manifest.update(extra_manifest)
        self._write_json(self.manifest_path, manifest)
        self._write_json(self.config_path, config)

    def record_cycle(self, result: CycleResult) -> None:
        event = {
            "run_id": self.run_id,
            "cycle_id": result.cycle_id,
            "mode": result.mode,
            "product_id": result.market.product_id,
            "timestamp": result.market.as_of,
            "market": result.market,
            "signal": result.signal,
            "target_position": result.signal.target_position,
            "risk_decision": result.risk_decision,
            "execution_summary": result.execution_summary,
            "no_trade_reason": result.no_trade_reason,
            "order_intent": result.order_intent,
            "fill": result.fill,
            "position": result.state,
        }
        self.append_event("cycle", event)
        if result.fill is not None:
            self._append_ndjson(
                self.fills_path,
                {
                    "run_id": self.run_id,
                    "cycle_id": result.cycle_id,
                    "fill": result.fill,
                },
            )
        self._append_position(result.cycle_id, result.state)
        self._write_json(
            self.state_path,
            {
                "run_id": self.run_id,
                "cycle_id": result.cycle_id,
                "mode": result.mode,
                "product_id": result.market.product_id,
                "signal": result.signal,
                "risk_decision": result.risk_decision,
                "execution_summary": result.execution_summary,
                "no_trade_reason": result.no_trade_reason,
                "order_intent": result.order_intent,
                "fill": result.fill,
                "position": result.state,
            },
        )
        LOGGER.info(json.dumps(_jsonable(event), sort_keys=True))

    def append_event(self, event_type: str, payload: Any) -> None:
        self._append_ndjson(
            self.events_path,
            {
                "event_type": event_type,
                **(payload if isinstance(payload, dict) else {"payload": payload}),
            },
        )

    def write_state(self, payload: Any) -> None:
        self._write_json(self.state_path, payload)

    def append_fill_row(self, payload: Any) -> None:
        self._append_ndjson(self.fills_path, payload)

    def append_position_row(self, payload: Any) -> None:
        self._append_ndjson(self.positions_path, payload)

    def _append_position(self, cycle_id: str, state: PositionState) -> None:
        self._append_ndjson(
            self.positions_path,
            {
                "run_id": self.run_id,
                "cycle_id": cycle_id,
                "position": state,
            },
        )

    def _append_ndjson(self, path: Path, payload: Any) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_jsonable(payload), sort_keys=True))
            handle.write("\n")

    def _write_json(self, path: Path, payload: Any) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(_jsonable(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
