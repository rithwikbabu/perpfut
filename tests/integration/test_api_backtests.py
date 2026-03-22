import json
from pathlib import Path

from fastapi.testclient import TestClient

from perpfut.api import create_app
from perpfut.api.backtest_manager import (
    BacktestJobConflictError,
    BacktestJobStartError,
    BacktestJobStateError,
)
from perpfut.api.schemas import BacktestJobStatusResponse, BacktestRunRequest


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ndjson(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def _make_backtest_run(runs_dir: Path, run_id: str, *, suite_id: str, strategy_id: str) -> None:
    run_dir = runs_dir / "backtests" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": f"{run_id}-created",
            "mode": "backtest",
            "product_id": "MULTI_ASSET",
            "dataset_id": "dataset-1",
            "suite_id": suite_id,
            "strategy_id": strategy_id,
        },
    )
    _write_json(
        run_dir / "state.json",
        {
            "run_id": run_id,
            "cycle_id": "cycle-0002",
            "mode": "backtest",
            "execution_summary": {
                "action": "filled",
                "reason_code": "filled",
                "reason_message": "filled",
                "summary": "filled",
            },
            "no_trade_reason": None,
            "position": {
                "equity_usdc": 10_100.0,
                "realized_pnl_usdc": 50.0,
                "unrealized_pnl_usdc": 50.0,
                "gross_notional_usdc": 4_000.0,
            },
            "portfolio": {
                "equity_usdc": 10_100.0,
                "realized_pnl_usdc": 50.0,
                "unrealized_pnl_usdc": 50.0,
                "gross_notional_usdc": 4_000.0,
            },
        },
    )
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "mode": "backtest",
            "product_id": "MULTI_ASSET",
            "strategy_id": strategy_id,
            "started_at": None,
            "ended_at": None,
            "cycle_count": 2,
            "starting_equity_usdc": 10000.0,
            "ending_equity_usdc": 10100.0,
            "realized_pnl_usdc": 50.0,
            "unrealized_pnl_usdc": 50.0,
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "max_drawdown_usdc": 5.0,
            "max_drawdown_pct": 0.001,
            "turnover_usdc": 1200.0,
            "fill_count": 2,
            "trade_count": 2,
            "avg_abs_exposure_pct": 0.15,
            "max_abs_exposure_pct": 0.25,
            "decision_counts": {"filled": 2},
            "equity_series": [{"label": "a", "value": 10000.0}, {"label": "b", "value": 10100.0}],
            "drawdown_series": [{"label": "a", "value": 0.0}, {"label": "b", "value": 5.0}],
            "exposure_series": [{"label": "a", "value": 0.1}, {"label": "b", "value": 0.2}],
        },
    )
    _write_ndjson(run_dir / "events.ndjson", [{"cycle_id": "cycle-0002", "sequence": 2}])
    _write_ndjson(run_dir / "fills.ndjson", [{"fill_id": "fill-1"}])
    _write_ndjson(run_dir / "positions.ndjson", [{"cycle_id": "cycle-0002", "position": {"equity_usdc": 10100.0}}])


def _make_backtest_suite(runs_dir: Path, suite_id: str, run_ids: list[str], strategies: list[str]) -> None:
    suite_dir = runs_dir / "backtests" / "suites" / suite_id
    suite_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        suite_dir / "manifest.json",
        {
            "suite_id": suite_id,
            "created_at": f"{suite_id}-created",
            "dataset_id": "dataset-1",
            "products": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
            "strategies": strategies,
            "run_ids": run_ids,
        },
    )


class StubBacktestManager:
    def __init__(self):
        self.started = None
        self.active = None

    def status(self) -> BacktestJobStatusResponse | None:
        return self.active

    def start(self, request: BacktestRunRequest) -> BacktestJobStatusResponse:
        self.started = request
        self.active = BacktestJobStatusResponse(
            job_id="job-1",
            status="running",
            pid=321,
            created_at="2026-03-22T00:00:00+00:00",
            started_at="2026-03-22T00:00:00+00:00",
            finished_at=None,
            suite_id=None,
            dataset_id=None,
            run_ids=[],
            error=None,
            log_path="runs/backtests/control/job-1.log",
            request=request,
        )
        return self.active


def test_backtests_list_and_detail_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    manager = StubBacktestManager()
    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: manager)
    _make_backtest_run(tmp_path, "run-2", suite_id="suite-1", strategy_id="momentum")
    _make_backtest_run(tmp_path, "run-1", suite_id="suite-1", strategy_id="mean_reversion")
    _make_backtest_suite(tmp_path, "suite-1", ["run-2", "run-1"], ["momentum", "mean_reversion"])
    client = TestClient(create_app())

    list_response = client.get("/api/backtests", params={"limit": 1})
    detail_response = client.get("/api/backtests/run-2")
    analysis_response = client.get("/api/backtests/run-2/analysis")
    events_response = client.get("/api/backtests/run-2/events", params={"limit": 1})
    suites_response = client.get("/api/backtest-suites")
    suite_detail_response = client.get("/api/backtest-suites/suite-1")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert list_response.json()["items"][0]["run_id"] == "run-2"

    assert detail_response.status_code == 200
    assert detail_response.json()["analysis"]["strategy_id"] == "momentum"

    assert analysis_response.status_code == 200
    assert analysis_response.json()["run_id"] == "run-2"

    assert events_response.status_code == 200
    assert events_response.json()["items"][0]["sequence"] == 2

    assert suites_response.status_code == 200
    assert suites_response.json()["items"][0]["suite_id"] == "suite-1"

    assert suite_detail_response.status_code == 200
    assert suite_detail_response.json()["items"][0]["rank"] == 1


def test_backtest_endpoints_return_empty_state_when_no_artifacts_exist(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: StubBacktestManager())
    client = TestClient(create_app())

    backtests_response = client.get("/api/backtests")
    suites_response = client.get("/api/backtest-suites")

    assert backtests_response.status_code == 200
    assert backtests_response.json() == {"items": [], "count": 0, "active_job": None}
    assert suites_response.status_code == 200
    assert suites_response.json() == {"items": [], "count": 0, "active_job": None}


def test_start_backtest_route_returns_job_status(monkeypatch) -> None:
    manager = StubBacktestManager()
    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: manager)
    client = TestClient(create_app())

    response = client.post(
        "/api/backtests",
        json={
            "productIds": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
            "strategyIds": ["momentum", "mean_reversion"],
            "start": "2026-03-20T00:00:00+00:00",
            "end": "2026-03-21T00:00:00+00:00",
            "granularity": "ONE_MINUTE",
            "startingCollateralUsdc": 10000,
        },
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-1"
    assert manager.started is not None
    assert manager.started.product_ids == ["BTC-PERP-INTX", "ETH-PERP-INTX"]


def test_backtest_routes_map_manager_failures(monkeypatch) -> None:
    class ConflictManager(StubBacktestManager):
        def start(self, request: BacktestRunRequest) -> BacktestJobStatusResponse:
            raise BacktestJobConflictError("a backtest job is already active")

    class BrokenStateManager(StubBacktestManager):
        def status(self) -> BacktestJobStatusResponse | None:
            raise BacktestJobStateError("backtest job metadata is corrupted")

    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: ConflictManager())
    client = TestClient(create_app())
    start_response = client.post(
        "/api/backtests",
        json={
            "productIds": ["BTC-PERP-INTX"],
            "strategyIds": ["momentum"],
            "start": "2026-03-20T00:00:00+00:00",
            "end": "2026-03-21T00:00:00+00:00",
            "granularity": "ONE_MINUTE",
        },
    )

    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: BrokenStateManager())
    list_response = client.get("/api/backtests")

    assert start_response.status_code == 409
    assert start_response.json()["detail"] == "a backtest job is already active"
    assert list_response.status_code == 500
    assert list_response.json()["detail"] == "backtest job metadata is corrupted"


def test_start_backtest_route_maps_start_failures(monkeypatch) -> None:
    class FailedStartManager(StubBacktestManager):
        def start(self, request: BacktestRunRequest) -> BacktestJobStatusResponse:
            raise BacktestJobStartError("backtest job exited immediately")

    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: FailedStartManager())
    client = TestClient(create_app())

    response = client.post(
        "/api/backtests",
        json={
            "productIds": ["BTC-PERP-INTX"],
            "strategyIds": ["momentum"],
            "start": "2026-03-20T00:00:00+00:00",
            "end": "2026-03-21T00:00:00+00:00",
            "granularity": "ONE_MINUTE",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "backtest job exited immediately"


def test_backtest_suite_detail_does_not_depend_on_paginated_suite_listing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: StubBacktestManager())
    _make_backtest_run(tmp_path, "run-2", suite_id="suite-1", strategy_id="momentum")
    _make_backtest_suite(tmp_path, "suite-1", ["run-2"], ["momentum"])
    monkeypatch.setattr("perpfut.api.repository.list_backtest_suites", lambda *_args, **_kwargs: [])
    client = TestClient(create_app())

    response = client.get("/api/backtest-suites/suite-1")

    assert response.status_code == 200
    assert response.json()["suite_id"] == "suite-1"


def test_backtest_run_detail_maps_invalid_analysis_payloads_to_500(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("perpfut.api.routers.backtests.get_backtest_job_manager", lambda: StubBacktestManager())
    run_dir = tmp_path / "backtests" / "runs" / "run-bad"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "run-bad",
            "mode": "backtest",
            "suite_id": "suite-1",
            "dataset_id": "dataset-1",
        },
    )
    _write_json(run_dir / "state.json", {"run_id": "run-bad"})
    _write_json(run_dir / "analysis.json", {"run_id": "run-bad", "fill_count": "bad"})
    client = TestClient(create_app())

    response = client.get("/api/backtests/run-bad")

    assert response.status_code == 500
    assert response.json()["detail"] == "invalid backtest analysis payload for: run-bad"
