import json

import pytest

from perpfut.api.process_manager import (
    PaperProcessManager,
    PaperRunConflictError,
    PaperRunStartError,
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
        iterations=5,
        intervalSeconds=60,
        startingCollateralUsdc=10_000.0,
    )


def test_start_persists_metadata_and_rejects_duplicate(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: DummyProcess(4321))
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_is_process_alive", lambda pid: pid == 4321)

    status = manager.start(_request())

    assert status.active is True
    payload = json.loads((tmp_path / "control" / "active_paper.json").read_text(encoding="utf-8"))
    assert payload["pid"] == 4321

    with pytest.raises(PaperRunConflictError):
        manager.start(_request())


def test_status_clears_stale_metadata(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True)
    metadata_path = control_dir / "active_paper.json"
    metadata_path.write_text(
        json.dumps(
            {
                "pid": 9999,
                "started_at": "2026-03-22T00:00:00+00:00",
                "run_id": None,
                "product_id": "BTC-PERP-INTX",
                "iterations": 5,
                "interval_seconds": 60,
                "starting_collateral_usdc": 10000.0,
                "log_path": str(control_dir / "paper.log"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(manager, "_is_process_alive", lambda _pid: False)

    status = manager.status()

    assert status.active is False
    assert not metadata_path.exists()


def test_stop_force_kills_when_process_survives_sigterm(monkeypatch, tmp_path) -> None:
    manager = PaperProcessManager(tmp_path)
    control_dir = tmp_path / "control"
    control_dir.mkdir(parents=True)
    metadata_path = control_dir / "active_paper.json"
    metadata_path.write_text(
        json.dumps(
            {
                "pid": 5678,
                "started_at": "2026-03-22T00:00:00+00:00",
                "run_id": None,
                "product_id": "BTC-PERP-INTX",
                "iterations": 5,
                "interval_seconds": 60,
                "starting_collateral_usdc": 10000.0,
                "log_path": str(control_dir / "paper.log"),
            }
        ),
        encoding="utf-8",
    )

    alive_states = iter([True, True, True, False])
    sent_signals = []
    monotonic_values = iter([0.0, 6.0, 6.1, 6.2, 6.3])

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
