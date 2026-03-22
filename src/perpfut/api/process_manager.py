"""Local process manager for paper trading runs."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .schemas import PaperRunRequest, PaperRunStatusResponse
from ..config import AppConfig


class PaperRunConflictError(RuntimeError):
    """Raised when a paper run is already active."""


class PaperRunStartError(RuntimeError):
    """Raised when a paper run fails to start."""


class PaperRunStopError(RuntimeError):
    """Raised when a paper run fails to stop cleanly."""


class PaperRunStateError(RuntimeError):
    """Raised when control-plane state is invalid or unavailable."""


@dataclass(frozen=True, slots=True)
class PaperProcessMetadata:
    pid: int
    started_at: str
    run_id: str | None
    product_id: str
    iterations: int
    interval_seconds: int
    starting_collateral_usdc: float
    log_path: str


class PaperProcessManager:
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.control_dir = runs_dir / "control"
        self.active_metadata_path = self.control_dir / "active_paper.json"
        self.lock_path = self.control_dir / "active_paper.lock"
        self.log_path = self.control_dir / "paper.log"

    def status(self) -> PaperRunStatusResponse:
        with self._control_lock():
            return self._status_locked()

    def start(self, request: PaperRunRequest) -> PaperRunStatusResponse:
        with self._control_lock():
            current = self._status_locked()
            if current.active:
                raise PaperRunConflictError("a paper run is already active")

            self.control_dir.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "perpfut",
                        "paper",
                        "--product-id",
                        request.product_id,
                        "--iterations",
                        str(request.iterations),
                        "--interval-seconds",
                        str(request.interval_seconds),
                    ],
                    cwd=Path.cwd(),
                    env=self._build_env(request),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            time.sleep(0.2)
            if process.poll() is not None:
                raise PaperRunStartError("paper process exited immediately; inspect runs/control/paper.log")

            metadata = PaperProcessMetadata(
                pid=process.pid,
                started_at=datetime.now(timezone.utc).isoformat(),
                run_id=None,
                product_id=request.product_id,
                iterations=request.iterations,
                interval_seconds=request.interval_seconds,
                starting_collateral_usdc=request.starting_collateral_usdc,
                log_path=str(self.log_path),
            )
            self._write_metadata(metadata)
            return self._to_status(metadata, active=True)

    def stop(self) -> PaperRunStatusResponse:
        with self._control_lock():
            metadata = self._load_metadata()
            if metadata is None:
                return PaperRunStatusResponse(active=False)

            if self._is_process_alive(metadata.pid):
                self._signal_process_group(metadata.pid, signal.SIGTERM)
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and self._is_process_alive(metadata.pid):
                    time.sleep(0.1)

                if self._is_process_alive(metadata.pid):
                    self._signal_process_group(metadata.pid, signal.SIGKILL)
                    deadline = time.monotonic() + 1.0
                    while time.monotonic() < deadline and self._is_process_alive(metadata.pid):
                        time.sleep(0.1)

                if self._is_process_alive(metadata.pid):
                    raise PaperRunStopError(
                        "paper process is still alive after SIGTERM/SIGKILL; inspect runs/control/paper.log"
                    )

            self._clear_metadata()
            return self._to_status(metadata, active=False)

    def _build_env(self, request: PaperRunRequest) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "MODE": "paper",
                "PRODUCT_ID": request.product_id,
                "ITERATIONS": str(request.iterations),
                "INTERVAL_SECONDS": str(request.interval_seconds),
                "STARTING_COLLATERAL_USDC": str(request.starting_collateral_usdc),
                "RUNS_DIR": str(self.runs_dir),
            }
        )
        return env

    def _status_locked(self) -> PaperRunStatusResponse:
        metadata = self._load_metadata()
        if metadata is None:
            return PaperRunStatusResponse(active=False)
        if not self._is_process_alive(metadata.pid):
            self._clear_metadata()
            return PaperRunStatusResponse(active=False)
        return self._to_status(metadata, active=True)

    def _load_metadata(self) -> PaperProcessMetadata | None:
        if not self.active_metadata_path.exists():
            return None
        try:
            payload = json.loads(self.active_metadata_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PaperRunStateError("failed to read paper run metadata") from exc
        except json.JSONDecodeError as exc:
            raise PaperRunStateError("paper run metadata is corrupted") from exc
        try:
            return PaperProcessMetadata(**payload)
        except TypeError as exc:
            raise PaperRunStateError("paper run metadata is invalid") from exc

    def _write_metadata(self, metadata: PaperProcessMetadata) -> None:
        self.control_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.control_dir / f"{self.active_metadata_path.name}.tmp"
        payload = json.dumps(asdict(metadata), indent=2, sort_keys=True)
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.active_metadata_path)
        except OSError as exc:
            raise PaperRunStateError("failed to persist paper run metadata") from exc
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def _clear_metadata(self) -> None:
        try:
            self.active_metadata_path.unlink()
        except FileNotFoundError:
            return

    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _signal_process_group(self, pid: int, sig: signal.Signals) -> None:
        try:
            os.killpg(os.getpgid(pid), sig)
        except ProcessLookupError:
            return

    @contextmanager
    def _control_lock(self):
        self.control_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5.0
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise PaperRunStateError("paper run control lock timed out")
                time.sleep(0.05)
            except OSError as exc:
                raise PaperRunStateError("failed to acquire paper run control lock") from exc

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
                handle.flush()
                os.fsync(handle.fileno())
            yield
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    def _to_status(self, metadata: PaperProcessMetadata, *, active: bool) -> PaperRunStatusResponse:
        return PaperRunStatusResponse(
            active=active,
            pid=metadata.pid,
            started_at=metadata.started_at,
            run_id=metadata.run_id,
            product_id=metadata.product_id,
            iterations=metadata.iterations,
            interval_seconds=metadata.interval_seconds,
            starting_collateral_usdc=metadata.starting_collateral_usdc,
            log_path=metadata.log_path,
        )


def get_paper_process_manager() -> PaperProcessManager:
    return PaperProcessManager(AppConfig.from_env().runtime.runs_dir)
