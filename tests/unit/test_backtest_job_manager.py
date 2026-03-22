import json

from perpfut.api.backtest_manager import BacktestJobManager, BacktestJobMetadata
from perpfut.api.schemas import BacktestRunRequest


def _request() -> BacktestRunRequest:
    return BacktestRunRequest.model_validate(
        {
            "productIds": ["BTC-PERP-INTX"],
            "strategyIds": ["momentum"],
            "start": "2026-03-20T00:00:00+00:00",
            "end": "2026-03-21T00:00:00+00:00",
            "granularity": "ONE_MINUTE",
        }
    )


def test_status_marks_orphaned_completed_job_as_succeeded(monkeypatch, tmp_path) -> None:
    manager = BacktestJobManager(tmp_path)
    request = _request()
    log_path = manager.control_dir / "job-1.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "suite_id": "suite-1",
                "dataset_id": "dataset-1",
                "run_ids": ["run-1", "run-2"],
            }
        ),
        encoding="utf-8",
    )
    metadata = BacktestJobMetadata(
        job_id="job-1",
        status="running",
        pid=12345,
        created_at="2026-03-22T00:00:00+00:00",
        started_at="2026-03-22T00:00:00+00:00",
        finished_at=None,
        suite_id=None,
        dataset_id=None,
        run_ids=(),
        error=None,
        log_path=str(log_path),
        request=request.model_dump(by_alias=True),
    )
    manager._write_metadata(manager.active_metadata_path, metadata)
    manager._write_metadata(manager.jobs_dir / "job-1.json", metadata)
    monkeypatch.setattr(manager, "_poll_process", lambda pid: (False, None))

    assert manager.status() is None

    jobs = manager.list_jobs(limit=1)
    assert jobs[0].status == "succeeded"
    assert jobs[0].suite_id == "suite-1"
    assert jobs[0].run_ids == ["run-1", "run-2"]


def test_status_marks_failed_job_and_surfaces_log_tail(monkeypatch, tmp_path) -> None:
    manager = BacktestJobManager(tmp_path)
    request = _request()
    log_path = manager.control_dir / "job-2.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line one\nterminal failure\n", encoding="utf-8")
    metadata = BacktestJobMetadata(
        job_id="job-2",
        status="running",
        pid=12346,
        created_at="2026-03-22T00:00:00+00:00",
        started_at="2026-03-22T00:00:00+00:00",
        finished_at=None,
        suite_id=None,
        dataset_id=None,
        run_ids=(),
        error=None,
        log_path=str(log_path),
        request=request.model_dump(by_alias=True),
    )
    manager._write_metadata(manager.active_metadata_path, metadata)
    manager._write_metadata(manager.jobs_dir / "job-2.json", metadata)
    monkeypatch.setattr(manager, "_poll_process", lambda pid: (False, 1))

    assert manager.status() is None

    jobs = manager.list_jobs(limit=1)
    assert jobs[0].status == "failed"
    assert jobs[0].error == "terminal failure"
