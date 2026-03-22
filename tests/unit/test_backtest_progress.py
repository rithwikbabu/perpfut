import json

from perpfut.backtest_progress import BacktestProgressReporter, BacktestProgressUpdate


def test_progress_reporter_updates_both_metadata_files(tmp_path) -> None:
    active_path = tmp_path / "active.json"
    job_path = tmp_path / "job.json"
    payload = {
        "job_id": "job-1",
        "status": "running",
        "phase": "queued",
        "phase_message": "Waiting",
        "created_at": "2026-03-22T00:00:00+00:00",
        "request": {},
        "log_path": "runs/backtests/control/job-1.log",
    }
    active_path.write_text(json.dumps(payload), encoding="utf-8")
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    reporter = BacktestProgressReporter(metadata_paths=(active_path, job_path))

    reporter.emit(
        BacktestProgressUpdate(
            phase="running_suite",
            phase_message="Completed strategy 1 of 2: momentum",
            total_runs=2,
            completed_runs=1,
        )
    )

    active = json.loads(active_path.read_text(encoding="utf-8"))
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert active["phase"] == "running_suite"
    assert active["total_runs"] == 2
    assert active["completed_runs"] == 1
    assert "last_heartbeat_at" in active
    assert job["phase_message"] == "Completed strategy 1 of 2: momentum"
