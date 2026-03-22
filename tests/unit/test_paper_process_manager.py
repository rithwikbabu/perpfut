import json
import os

import pytest

from perpfut.api.process_manager import (
    PaperProcessManager,
    PaperRunConflictError,
    PaperRunStateError,
    PaperRunStartError,
    PaperRunStopError,
)
from perpfut.api.schemas import PaperRunRequest


class DummyProcess:
    def __init__(self, pid: int, *, poll_result=None):
        self.pid = pid
        self._poll_result = poll_result

    def poll(self):
        return self._poll_result


def _request() -> PaperRunRequest:
    return PaperRunRequest(
        productId="BTC-PERP-INTX",
        strategyId="momentum",
        iterations=5,
        intervalSeconds=60,
        startingCollateralUsdc=10_000.0,
    )


def _write_metadata(tmp_path, *, pid: int = 5678) -> None:
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "active_paper.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "started_at": "2026-03-22T00:00:00+00:00",
                "run_id": None,
                "product_id": "BTC-PERP-INTX",
                "strategy_id": "momentum",
                "iterations": 5,
                "interval_seconds": 60,
                "starting_collateral_usdc": 10000.0,
                "log_path": str(control_dir / "paper.log"),
            }
        ),
        encoding="utf-8",
    )


def test_start_persists_metadata_and_rejects_duplicate(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: DummyProcess(4321))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_is_process_alive", lambda pid: pid == 4321)

    status = manager.start(_request())

    assert status.active is True
    assert status.strategy_id == "momentum"
    payload = json.loads((tmp_path / "control" / "active_paper.json").read_text(encoding="utf-8"))
    assert payload["pid"] == 4321
    assert payload["strategy_id"] == "momentum"

    with pytest.raises(PaperRunConflictError):
        manager.start(_request())


def test_status_clears_stale_metadata(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path, pid=9999)
    metadata_path = tmp_path / "control" / "active_paper.json"
    monkeypatch.setattr(manager, "_is_process_alive", lambda _pid: False)

    status = manager.status()

    assert status.active is False
    assert not metadata_path.exists()


def test_stop_force_kills_when_process_survives_sigterm(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path)
    metadata_path = tmp_path / "control" / "active_paper.json"

    alive_states = iter([True, True, True, False, False])
    sent_signals = []
    monotonic_values = iter([0.0, 0.1, 6.0, 6.1, 6.2, 7.2])

    monkeypatch.setattr(manager, "_is_process_alive", lambda _pid: next(alive_states, False))
    monkeypatch.setattr(manager, "_signal_process_group", lambda pid, sig: sent_signals.append((pid, sig.name)))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values, 6.4))

    status = manager.stop()

    assert status.active is False
    assert sent_signals == [(5678, "SIGTERM"), (5678, "SIGKILL")]
    assert not metadata_path.exists()


def test_start_raises_if_process_exits_immediately(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: DummyProcess(7654, poll_result=1))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(PaperRunStartError):
        manager.start(_request())


def test_start_rejects_unknown_strategy_before_spawning(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    started = {"called": False}

    def fake_popen(*args, **kwargs):
        started["called"] = True
        return DummyProcess(7654)

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    with pytest.raises(PaperRunStartError, match="unknown strategy_id"):
        manager.start(
            PaperRunRequest(
                productId="BTC-PERP-INTX",
                strategyId="unknown",
                iterations=5,
                intervalSeconds=60,
                startingCollateralUsdc=10_000.0,
            )
        )

    assert started["called"] is False


def test_status_raises_for_corrupted_metadata(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = control_dir / "active_paper.json"
    metadata_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(PaperRunStateError, match="corrupted"):
        manager.status()

    assert metadata_path.exists()


def test_stop_raises_and_preserves_metadata_if_process_survives(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path)
    metadata_path = tmp_path / "control" / "active_paper.json"
    sent_signals = []
    monotonic_values = iter([0.0, 0.1, 6.0, 6.1, 7.2])

    monkeypatch.setattr(manager, "_is_process_alive", lambda _pid: True)
    monkeypatch.setattr(manager, "_signal_process_group", lambda pid, sig: sent_signals.append((pid, sig.name)))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values, 7.3))

    with pytest.raises(PaperRunStopError, match="still alive"):
        manager.stop()

    assert sent_signals == [(5678, "SIGTERM"), (5678, "SIGKILL")]
    assert metadata_path.exists()


def test_status_raises_when_control_lock_times_out(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    lock_path = control_dir / "active_paper.lock"
    lock_path.write_text("", encoding="utf-8")
    monotonic_values = iter([0.0, 5.1])

    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values, 5.2))
    monkeypatch.setattr("time.time", lambda: lock_path.stat().st_mtime)

    with pytest.raises(PaperRunStateError, match="lock timed out"):
        manager.status()


def test_status_reaps_stale_control_lock(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    lock_path = control_dir / "active_paper.lock"
    lock_path.write_text("9999", encoding="utf-8")

    monkeypatch.setattr(manager, "_is_process_alive", lambda pid: False)

    status = manager.status()

    assert status.active is False
    assert not lock_path.exists()


def test_status_reaps_old_empty_control_lock(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    lock_path = control_dir / "active_paper.lock"
    lock_path.write_text("", encoding="utf-8")
    old_timestamp = lock_path.stat().st_mtime - manager.lock_stale_after_seconds - 1.0
    os.utime(lock_path, (old_timestamp, old_timestamp))

    monkeypatch.setattr("time.time", lambda: old_timestamp + manager.lock_stale_after_seconds + 2.0)

    status = manager.status()

    assert status.active is False
    assert not lock_path.exists()


def test_status_reaps_dead_child_process(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path, pid=4321)
    metadata_path = tmp_path / "control" / "active_paper.json"

    monkeypatch.setattr("os.waitpid", lambda pid, flags: (pid, 0))

    status = manager.status()

    assert status.active is False
    assert not metadata_path.exists()


def test_stop_succeeds_when_child_is_already_a_zombie(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path, pid=4321)
    metadata_path = tmp_path / "control" / "active_paper.json"
    waitpid_results = iter([(0, 0), (4321, 0)])

    monkeypatch.setattr("os.waitpid", lambda pid, flags: next(waitpid_results))
    monkeypatch.setattr(PaperProcessManager, "_get_process_state", lambda self, pid: None)
    monkeypatch.setattr(manager, "_signal_process_group", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    status = manager.stop()

    assert status.active is False
    assert not metadata_path.exists()


def test_status_treats_zombie_process_state_as_inactive(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    _write_metadata(tmp_path, pid=4321)
    metadata_path = tmp_path / "control" / "active_paper.json"
    reaped = []

    monkeypatch.setattr("os.waitpid", lambda pid, flags: reaped.append((pid, flags)) or (0, 0))
    monkeypatch.setattr(PaperProcessManager, "_get_process_state", lambda self, pid: "Z")

    status = manager.status()

    assert status.active is False
    assert not metadata_path.exists()
    assert reaped == [(4321, os.WNOHANG), (4321, os.WNOHANG)]
