"""Local process manager for historical backtest jobs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .schemas import BacktestJobStatusResponse, BacktestRunRequest
from ..config import AppConfig
from ..strategy_registry import validate_strategy_id


class BacktestJobConflictError(RuntimeError):
    """Raised when a backtest job is already active."""


class BacktestJobStartError(RuntimeError):
    """Raised when a backtest job cannot be launched."""


class BacktestJobStateError(RuntimeError):
    """Raised when backtest control-plane state is invalid."""


@dataclass(frozen=True, slots=True)
class BacktestJobMetadata:
    job_id: str
    status: str
    phase: str | None
    phase_message: str | None
    pid: int | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    total_runs: int | None
    completed_runs: int | None
    last_heartbeat_at: str | None
    suite_id: str | None
    dataset_id: str | None
    run_ids: tuple[str, ...]
    error: str | None
    log_path: str
    request: dict[str, object]


class BacktestJobManager:
    lock_stale_after_seconds = 10.0

    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.backtests_dir = runs_dir / "backtests"
        self.control_dir = self.backtests_dir / "control"
        self.jobs_dir = self.control_dir / "jobs"
        self.active_metadata_path = self.control_dir / "active_backtest.json"
        self.lock_path = self.control_dir / "active_backtest.lock"

    def status(self) -> BacktestJobStatusResponse | None:
        with self._control_lock():
            return self._active_status_locked()

    def list_jobs(self, *, limit: int = 10) -> list[BacktestJobStatusResponse]:
        with self._control_lock():
            active = self._active_status_locked()
            jobs: list[BacktestJobStatusResponse] = []
            if self.jobs_dir.exists():
                for path in sorted((item for item in self.jobs_dir.iterdir() if item.suffix == ".json"), reverse=True):
                    metadata = self._load_metadata(path)
                    jobs.append(self._to_status(metadata))
                    if len(jobs) >= limit:
                        break
            if active is not None and all(item.job_id != active.job_id for item in jobs):
                jobs.insert(0, active)
            return jobs[:limit]

    def start(self, request: BacktestRunRequest) -> BacktestJobStatusResponse:
        with self._control_lock():
            current = self._active_status_locked()
            if current is not None and current.status == "running":
                raise BacktestJobConflictError("a backtest job is already active")

            for strategy_id in request.strategy_ids:
                try:
                    validate_strategy_id(strategy_id)
                except ValueError as exc:
                    raise BacktestJobStartError(str(exc)) from exc

            self.control_dir.mkdir(parents=True, exist_ok=True)
            self.jobs_dir.mkdir(parents=True, exist_ok=True)
            created_at = datetime.now(timezone.utc)
            job_id = created_at.strftime("%Y%m%dT%H%M%S%fZ")
            log_path = self.control_dir / f"{job_id}.log"
            command = self._build_command(request)
            with log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    command,
                    cwd=Path.cwd(),
                    env=self._build_env(job_id=job_id),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            time.sleep(0.2)
            if process.poll() is not None:
                raise BacktestJobStartError("backtest job exited immediately; inspect runs/backtests/control logs")

            metadata = BacktestJobMetadata(
                job_id=job_id,
                status="running",
                phase="queued",
                phase_message="Waiting for backtest worker heartbeat.",
                pid=process.pid,
                created_at=created_at.isoformat(),
                started_at=created_at.isoformat(),
                finished_at=None,
                total_runs=len(request.strategy_ids),
                completed_runs=0,
                last_heartbeat_at=created_at.isoformat(),
                suite_id=None,
                dataset_id=None,
                run_ids=(),
                error=None,
                log_path=str(log_path),
                request=request.model_dump(by_alias=True),
            )
            self._write_metadata(self.active_metadata_path, metadata)
            self._write_metadata(self.jobs_dir / f"{job_id}.json", metadata)
            return self._to_status(metadata)

    def _build_command(self, request: BacktestRunRequest) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "perpfut",
            "backtest",
            "run",
            "--runs-dir",
            str(self.runs_dir),
            "--start",
            request.start,
            "--end",
            request.end,
            "--granularity",
            request.granularity,
        ]
        for product_id in request.product_ids:
            command.extend(["--product-id", product_id])
        for strategy_id in request.strategy_ids:
            command.extend(["--strategy-id", strategy_id])
        if request.lookback_candles is not None:
            command.extend(["--lookback-candles", str(request.lookback_candles)])
        if request.signal_scale is not None:
            command.extend(["--signal-scale", str(request.signal_scale)])
        if request.starting_collateral_usdc is not None:
            command.extend(["--starting-collateral-usdc", str(request.starting_collateral_usdc)])
        if request.max_abs_position is not None:
            command.extend(["--max-abs-position", str(request.max_abs_position)])
        if request.max_gross_position is not None:
            command.extend(["--max-gross-position", str(request.max_gross_position)])
        if request.max_leverage is not None:
            command.extend(["--max-leverage", str(request.max_leverage)])
        if request.slippage_bps is not None:
            command.extend(["--slippage-bps", str(request.slippage_bps)])
        return command

    def _build_env(self, *, job_id: str) -> dict[str, str]:
        env = os.environ.copy()
        env["RUNS_DIR"] = str(self.runs_dir)
        env["PERPFUT_BACKTEST_ACTIVE_METADATA_PATH"] = str(self.active_metadata_path)
        env["PERPFUT_BACKTEST_JOB_METADATA_PATH"] = str(self.jobs_dir / f"{job_id}.json")
        return env

    def _active_status_locked(self) -> BacktestJobStatusResponse | None:
        metadata = self._load_active_metadata()
        if metadata is None:
            return None
        refreshed = self._refresh_metadata(metadata)
        if refreshed.status != "running":
            self._clear_active_metadata()
            self._write_metadata(self.jobs_dir / f"{refreshed.job_id}.json", refreshed)
            return None
        return self._to_status(refreshed)

    def _refresh_metadata(self, metadata: BacktestJobMetadata) -> BacktestJobMetadata:
        if metadata.status != "running" or metadata.pid is None:
            return metadata
        alive, exit_code = self._poll_process(metadata.pid)
        if alive:
            return metadata
        return self._finalize_metadata(metadata, exit_code=exit_code)

    def _finalize_metadata(self, metadata: BacktestJobMetadata, *, exit_code: int | None) -> BacktestJobMetadata:
        finished_at = datetime.now(timezone.utc).isoformat()
        log_path = Path(metadata.log_path)
        success_payload = self._try_load_success_payload(log_path)
        if exit_code == 0 or (exit_code is None and success_payload is not None):
            payload = success_payload
            if payload is None:
                raise BacktestJobStateError("backtest job output is invalid")
            return BacktestJobMetadata(
                job_id=metadata.job_id,
                status="succeeded",
                phase="succeeded",
                phase_message="Backtest suite completed successfully.",
                pid=None,
                created_at=metadata.created_at,
                started_at=metadata.started_at,
                finished_at=finished_at,
                total_runs=metadata.total_runs,
                completed_runs=metadata.completed_runs,
                last_heartbeat_at=metadata.last_heartbeat_at,
                suite_id=_as_str(payload.get("suite_id")),
                dataset_id=_as_str(payload.get("dataset_id")),
                run_ids=tuple(_as_str_list(payload.get("run_ids"))),
                error=None,
                log_path=metadata.log_path,
                request=metadata.request,
            )
        return BacktestJobMetadata(
            job_id=metadata.job_id,
            status="failed",
            phase="failed",
            phase_message="Backtest suite failed.",
            pid=None,
            created_at=metadata.created_at,
            started_at=metadata.started_at,
            finished_at=finished_at,
            total_runs=metadata.total_runs,
            completed_runs=metadata.completed_runs,
            last_heartbeat_at=metadata.last_heartbeat_at,
            suite_id=None,
            dataset_id=None,
            run_ids=(),
            error=self._tail_log_message(log_path),
            log_path=metadata.log_path,
            request=metadata.request,
        )

    def _poll_process(self, pid: int) -> tuple[bool, int | None]:
        try:
            waited_pid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            waited_pid, status = (0, None)
        except OSError as exc:
            raise BacktestJobStateError("failed to inspect backtest process state") from exc

        if waited_pid == pid:
            return False, os.waitstatus_to_exitcode(status)

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False, None
        except PermissionError:
            return True, None
        return True, None

    def _try_load_success_payload(self, log_path: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(log_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _tail_log_message(self, log_path: Path) -> str:
        try:
            lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except FileNotFoundError:
            return "backtest job failed; log file is missing"
        except OSError:
            return "backtest job failed; inspect runs/backtests/control logs"
        if not lines:
            return "backtest job failed; inspect runs/backtests/control logs"
        return lines[-1]

    def _load_active_metadata(self) -> BacktestJobMetadata | None:
        if not self.active_metadata_path.exists():
            return None
        return self._load_metadata(self.active_metadata_path)

    def _load_metadata(self, path: Path) -> BacktestJobMetadata:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise BacktestJobStateError("failed to read backtest job metadata") from exc
        except json.JSONDecodeError as exc:
            raise BacktestJobStateError("backtest job metadata is corrupted") from exc
        try:
            return BacktestJobMetadata(
                job_id=str(payload["job_id"]),
                status=str(payload["status"]),
                phase=_as_str(payload.get("phase")),
                phase_message=_as_str(payload.get("phase_message")),
                pid=int(payload["pid"]) if payload.get("pid") is not None else None,
                created_at=str(payload["created_at"]),
                started_at=_as_str(payload.get("started_at")),
                finished_at=_as_str(payload.get("finished_at")),
                total_runs=_as_int(payload.get("total_runs")),
                completed_runs=_as_int(payload.get("completed_runs")),
                last_heartbeat_at=_as_str(payload.get("last_heartbeat_at")),
                suite_id=_as_str(payload.get("suite_id")),
                dataset_id=_as_str(payload.get("dataset_id")),
                run_ids=tuple(_as_str_list(payload.get("run_ids"))),
                error=_as_str(payload.get("error")),
                log_path=str(payload["log_path"]),
                request=_coerce_dict(payload.get("request")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BacktestJobStateError("backtest job metadata is invalid") from exc

    def _write_metadata(self, path: Path, metadata: BacktestJobMetadata) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        payload = json.dumps(asdict(metadata), indent=2, sort_keys=True)
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except OSError as exc:
            raise BacktestJobStateError("failed to persist backtest job metadata") from exc
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def _clear_active_metadata(self) -> None:
        try:
            self.active_metadata_path.unlink()
        except FileNotFoundError:
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
                self._reap_stale_lock()
                if time.monotonic() >= deadline:
                    raise BacktestJobStateError("backtest control lock timed out")
                time.sleep(0.05)
            except OSError as exc:
                raise BacktestJobStateError("failed to acquire backtest control lock") from exc

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

    def _reap_stale_lock(self) -> None:
        try:
            stat_result = self.lock_path.stat()
            lock_age_seconds = max(time.time() - stat_result.st_mtime, 0.0)
            payload = self.lock_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise BacktestJobStateError("failed to inspect backtest control lock") from exc

        if not payload:
            if lock_age_seconds >= self.lock_stale_after_seconds:
                self._remove_lock_file()
            return
        try:
            pid = int(payload)
        except ValueError:
            if lock_age_seconds >= self.lock_stale_after_seconds:
                self._remove_lock_file()
            return
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            self._remove_lock_file()
        except PermissionError:
            return

    def _remove_lock_file(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise BacktestJobStateError("failed to clear stale backtest control lock") from exc

    def _to_status(self, metadata: BacktestJobMetadata) -> BacktestJobStatusResponse:
        elapsed_seconds = _compute_elapsed_seconds(
            started_at=metadata.started_at,
            finished_at=metadata.finished_at,
        )
        progress_pct = _compute_progress_pct(
            total_runs=metadata.total_runs,
            completed_runs=metadata.completed_runs,
        )
        eta_seconds = _compute_eta_seconds(
            status=metadata.status,
            phase=metadata.phase,
            elapsed_seconds=elapsed_seconds,
            total_runs=metadata.total_runs,
            completed_runs=metadata.completed_runs,
        )
        return BacktestJobStatusResponse(
            job_id=metadata.job_id,
            status=metadata.status,
            phase=metadata.phase,
            phase_message=metadata.phase_message,
            pid=metadata.pid,
            created_at=metadata.created_at,
            started_at=metadata.started_at,
            finished_at=metadata.finished_at,
            total_runs=metadata.total_runs,
            completed_runs=metadata.completed_runs,
            progress_pct=progress_pct,
            elapsed_seconds=elapsed_seconds,
            eta_seconds=eta_seconds,
            last_heartbeat_at=metadata.last_heartbeat_at,
            suite_id=metadata.suite_id,
            dataset_id=metadata.dataset_id,
            run_ids=list(metadata.run_ids),
            error=metadata.error,
            log_path=metadata.log_path,
            request=BacktestRunRequest.model_validate(metadata.request),
        )


def get_backtest_job_manager() -> BacktestJobManager:
    return BacktestJobManager(AppConfig.from_env().runtime.runs_dir)


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _coerce_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _compute_elapsed_seconds(*, started_at: str | None, finished_at: str | None) -> float | None:
    start = _parse_timestamp(started_at)
    if start is None:
        return None
    end = _parse_timestamp(finished_at) or datetime.now(timezone.utc)
    return max((end - start).total_seconds(), 0.0)


def _compute_progress_pct(*, total_runs: int | None, completed_runs: int | None) -> float | None:
    if total_runs is None or total_runs <= 0:
        return None
    completed = min(max(completed_runs or 0, 0), total_runs)
    return completed / total_runs


def _compute_eta_seconds(
    *,
    status: str,
    phase: str | None,
    elapsed_seconds: float | None,
    total_runs: int | None,
    completed_runs: int | None,
) -> float | None:
    if status != "running":
        return 0.0 if elapsed_seconds is not None else None
    if phase not in {"running_suite", "finalizing"}:
        return None
    if elapsed_seconds is None or total_runs is None or total_runs <= 0:
        return None
    completed = min(max(completed_runs or 0, 0), total_runs)
    if completed <= 0:
        return None
    if completed >= total_runs:
        return 0.0
    average_seconds_per_run = elapsed_seconds / completed
    remaining_runs = total_runs - completed
    return max(average_seconds_per_run * remaining_runs, 0.0)


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
