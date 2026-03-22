import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from perpfut.api import create_app


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_portfolio_run(runs_dir: Path, run_id: str) -> None:
    run_dir = runs_dir / "backtests" / "portfolio-runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": "2026-03-22T00:00:00+00:00",
            "dataset_id": "dataset-1",
            "strategy_instance_ids": ["mom-a"],
            "sleeve_run_ids": ["sleeve-run-1"],
        },
    )
    _write_json(run_dir / "config.json", {"optimizer": {"lookback_days": 60}})
    _write_json(run_dir / "state.json", {"run_id": run_id, "ending_equity_usdc": 10100.0})
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "dataset_id": "dataset-1",
            "dataset_fingerprint": "fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "created_at": "2026-03-22T00:00:00+00:00",
            "starting_capital_usdc": 10000.0,
            "ending_equity_usdc": 10100.0,
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "sharpe_ratio": 1.5,
            "max_drawdown_usdc": 10.0,
            "max_drawdown_pct": 0.001,
            "total_turnover_usdc": 500.0,
            "transaction_cost_total_usdc": 5.0,
            "avg_gross_weight": 0.5,
            "max_gross_weight": 0.8,
            "strategy_instance_ids": ["mom-a"],
            "sleeve_run_ids": ["sleeve-run-1"],
            "equity_series": [{"label": "2026-03-20", "value": 10100.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "gross_return_series": [{"label": "2026-03-20", "value": 0.01}],
            "net_return_series": [{"label": "2026-03-20", "value": 0.01}],
            "turnover_series_usdc": [{"label": "2026-03-20", "value": 500.0}],
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
            "gross_weight_series": [{"label": "2026-03-20", "value": 0.5}],
            "contribution_totals_usdc": {"mom-a": 100.0},
        },
    )
    (run_dir / "weights.ndjson").write_text(
        json.dumps({"date": "2026-03-20", "weights": {"mom-a": 0.5}, "cash_weight": 0.5, "turnover": 0.5, "gross_weight": 0.5}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "diagnostics.ndjson").write_text(
        json.dumps({"date": "2026-03-20", "expected_returns": {"mom-a": 0.01}, "covariance_matrix": {"mom-a": {"mom-a": 0.001}}, "constraint_status": "optimized"}) + "\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "contributions.json",
        {
            "items": [
                {
                    "strategy_instance_id": "mom-a",
                    "strategy_id": "momentum",
                    "sleeve_run_id": "sleeve-run-1",
                    "total_gross_pnl_usdc": 100.0,
                    "daily_gross_pnl_series": [{"label": "2026-03-20", "value": 100.0}],
                }
            ],
            "transaction_cost_total_usdc": 5.0,
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
        },
    )


def _write_sleeve_run(
    runs_dir: Path,
    run_id: str,
    *,
    dataset_id: str = "dataset-1",
    strategy_instance_id: str = "mom-a",
    strategy_id: str = "momentum",
) -> None:
    run_dir = runs_dir / "backtests" / "sleeves" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": "2026-03-22T00:00:00+00:00",
            "dataset_id": dataset_id,
            "strategy_instance": {
                "strategy_instance_id": strategy_instance_id,
                "strategy_id": strategy_id,
                "universe": ["BTC-PERP-INTX"],
                "strategy_params": {},
                "risk_overrides": {},
            },
            "strategy_instance_id": strategy_instance_id,
        },
    )
    _write_json(run_dir / "state.json", {"run_id": run_id})
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "mode": "backtest",
            "product_id": "MULTI_ASSET",
            "strategy_id": strategy_id,
            "started_at": "2026-03-20T00:00:00+00:00",
            "ended_at": "2026-03-21T00:00:00+00:00",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "sharpe_ratio": 1.0,
            "cycle_count": 1,
            "starting_equity_usdc": 10000.0,
            "ending_equity_usdc": 10100.0,
            "realized_pnl_usdc": 100.0,
            "unrealized_pnl_usdc": 0.0,
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "max_drawdown_usdc": 10.0,
            "max_drawdown_pct": 0.001,
            "turnover_usdc": 100.0,
            "fill_count": 1,
            "trade_count": 1,
            "avg_abs_exposure_pct": 0.5,
            "max_abs_exposure_pct": 0.5,
            "decision_counts": {"filled": 1},
            "equity_series": [{"label": "2026-03-20", "value": 10100.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "exposure_series": [{"label": "2026-03-20", "value": 0.5}],
        },
    )
    _write_json(
        run_dir / "sleeve_analysis.json",
        {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_fingerprint": "fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "strategy_instance_id": strategy_instance_id,
            "strategy_id": strategy_id,
            "config_fingerprint": "cfg-1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "max_drawdown_usdc": 10.0,
            "max_drawdown_pct": 0.001,
            "daily_returns": [{"label": "2026-03-20", "value": 0.01}],
            "daily_turnover_usdc": [{"label": "2026-03-20", "value": 100.0}],
            "daily_avg_abs_exposure_pct": [{"label": "2026-03-20", "value": 0.5}],
            "daily_drawdown_usdc": [{"label": "2026-03-20", "value": 0.0}],
            "asset_contributions": [
                {
                    "product_id": "BTC-PERP-INTX",
                    "total_pnl_usdc": 100.0,
                    "daily_pnl_series": [{"label": "2026-03-20", "value": 100.0}],
                }
            ],
        },
    )


def test_portfolio_run_endpoints_list_detail_compare_and_create(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _write_portfolio_run(tmp_path, "portfolio-run-1")
    client = TestClient(create_app())

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            self.base_runs_dir = base_runs_dir

        def load_dataset(self, dataset_id):
            return SimpleNamespace(
                dataset_id=dataset_id,
                fingerprint="fp-1",
                source="coinbase",
                version="1",
                start=SimpleNamespace(isoformat=lambda: "2026-03-20T00:00:00+00:00"),
                end=SimpleNamespace(isoformat=lambda: "2026-03-21T00:00:00+00:00"),
            )

    def fake_run_portfolio_research(**kwargs):
        _write_portfolio_run(tmp_path, "portfolio-run-created")
        return SimpleNamespace(run_id="portfolio-run-created")

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr("perpfut.api.routers.backtests.run_portfolio_research", fake_run_portfolio_research)
    monkeypatch.setattr(
        "perpfut.api.routers.backtests.run_portfolio_research_from_sleeves",
        fake_run_portfolio_research,
    )

    _write_sleeve_run(tmp_path, "sleeve-run-1")

    list_response = client.get("/api/portfolio-runs")
    detail_response = client.get("/api/portfolio-runs/portfolio-run-1")
    analysis_response = client.get("/api/portfolio-runs/portfolio-run-1/analysis")
    compare_response = client.get("/api/portfolio-run-comparisons")
    create_response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "strategyInstances": [
                {
                    "strategyInstanceId": "mom-a",
                    "strategyId": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                }
            ],
        },
    )
    existing_sleeve_response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "sleeveRunIds": ["sleeve-run-1"],
        },
    )

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["run_id"] == "portfolio-run-1"
    assert detail_response.status_code == 200
    assert detail_response.json()["analysis"]["sharpe_ratio"] == 1.5
    assert analysis_response.status_code == 200
    assert analysis_response.json()["run_id"] == "portfolio-run-1"
    assert compare_response.status_code == 200
    assert compare_response.json()["items"][0]["run_id"] == "portfolio-run-1"
    assert create_response.status_code == 201
    assert create_response.json()["run_id"] == "portfolio-run-created"
    assert existing_sleeve_response.status_code == 201
    assert existing_sleeve_response.json()["analysis"]["sleeve_run_ids"] == ["sleeve-run-1"]


def test_portfolio_run_create_rejects_mixed_or_empty_modes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    client = TestClient(create_app())

    mixed_response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "strategyInstances": [
                {
                    "strategyInstanceId": "mom-a",
                    "strategyId": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                }
            ],
            "sleeveRunIds": ["sleeve-run-1"],
        },
    )
    empty_response = client.post(
        "/api/portfolio-runs",
        json={"datasetId": "dataset-1"},
    )

    assert mixed_response.status_code == 422
    assert "exactly one of strategyInstances or sleeveRunIds" in mixed_response.text
    assert empty_response.status_code == 422
    assert "exactly one of strategyInstances or sleeveRunIds" in empty_response.text


def test_portfolio_run_create_rejects_cross_dataset_sleeves(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _write_sleeve_run(tmp_path, "sleeve-run-1", dataset_id="dataset-1")
    _write_sleeve_run(tmp_path, "sleeve-run-2", dataset_id="dataset-2", strategy_instance_id="mr-b", strategy_id="mean_reversion")
    client = TestClient(create_app())

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            self.base_runs_dir = base_runs_dir

        def load_dataset(self, dataset_id):
            return SimpleNamespace(
                dataset_id=dataset_id,
                fingerprint="fp-1",
                source="coinbase",
                version="1",
                start=SimpleNamespace(isoformat=lambda: "2026-03-20T00:00:00+00:00"),
                end=SimpleNamespace(isoformat=lambda: "2026-03-21T00:00:00+00:00"),
            )

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)

    response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "sleeveRunIds": ["sleeve-run-1", "sleeve-run-2"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "selected sleeve runs must all belong to the same dataset"


def test_portfolio_run_create_rejects_duplicate_strategy_instance_ids(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _write_sleeve_run(tmp_path, "sleeve-run-1", dataset_id="dataset-1", strategy_instance_id="shared")
    _write_sleeve_run(
        tmp_path,
        "sleeve-run-2",
        dataset_id="dataset-1",
        strategy_instance_id="shared",
        strategy_id="mean_reversion",
    )
    client = TestClient(create_app())

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            self.base_runs_dir = base_runs_dir

        def load_dataset(self, dataset_id):
            return SimpleNamespace(
                dataset_id=dataset_id,
                fingerprint="fp-1",
                source="coinbase",
                version="1",
                start=SimpleNamespace(isoformat=lambda: "2026-03-20T00:00:00+00:00"),
                end=SimpleNamespace(isoformat=lambda: "2026-03-21T00:00:00+00:00"),
            )

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)

    response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "sleeveRunIds": ["sleeve-run-1", "sleeve-run-2"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "selected sleeve runs contain duplicate strategy_instance_id 'shared'"
    )
