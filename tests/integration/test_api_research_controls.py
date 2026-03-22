import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from perpfut.api import create_app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_sleeve_run(
    runs_dir: Path,
    run_id: str,
    *,
    dataset_id: str,
    strategy_instance_id: str,
    strategy_id: str,
) -> None:
    run_dir = runs_dir / "backtests" / "sleeves" / run_id
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
            "sharpe_ratio": 1.1,
            "cycle_count": 1,
            "starting_equity_usdc": 10000.0,
            "ending_equity_usdc": 10100.0,
            "realized_pnl_usdc": 100.0,
            "unrealized_pnl_usdc": 0.0,
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "max_drawdown_usdc": 12.0,
            "max_drawdown_pct": 0.0012,
            "turnover_usdc": 150.0,
            "fill_count": 1,
            "trade_count": 1,
            "avg_abs_exposure_pct": 0.25,
            "max_abs_exposure_pct": 0.25,
            "decision_counts": {"filled": 1},
            "equity_series": [{"label": "2026-03-20", "value": 10100.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "exposure_series": [{"label": "2026-03-20", "value": 0.25}],
        },
    )
    _write_json(
        run_dir / "sleeve_analysis.json",
        {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_fingerprint": "dataset-fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "strategy_instance_id": strategy_instance_id,
            "strategy_id": strategy_id,
            "config_fingerprint": "cfg-1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "max_drawdown_usdc": 12.0,
            "max_drawdown_pct": 0.0012,
            "daily_returns": [{"label": "2026-03-20", "value": 0.01}],
            "daily_turnover_usdc": [{"label": "2026-03-20", "value": 150.0}],
            "daily_avg_abs_exposure_pct": [{"label": "2026-03-20", "value": 0.25}],
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


def _write_portfolio_run(
    runs_dir: Path,
    run_id: str,
    *,
    dataset_id: str,
    sleeve_run_ids: list[str],
    strategy_instance_ids: list[str],
) -> None:
    run_dir = runs_dir / "backtests" / "portfolio-runs" / run_id
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": "2026-03-22T00:00:00+00:00",
            "dataset_id": dataset_id,
            "strategy_instance_ids": strategy_instance_ids,
            "sleeve_run_ids": sleeve_run_ids,
        },
    )
    _write_json(run_dir / "config.json", {"optimizer": {"lookback_days": 60}})
    _write_json(run_dir / "state.json", {"run_id": run_id, "ending_equity_usdc": 10150.0})
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "dataset_fingerprint": "dataset-fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "created_at": "2026-03-22T00:00:00+00:00",
            "starting_capital_usdc": 10000.0,
            "ending_equity_usdc": 10150.0,
            "total_pnl_usdc": 150.0,
            "total_return_pct": 0.015,
            "sharpe_ratio": 1.6,
            "max_drawdown_usdc": 10.0,
            "max_drawdown_pct": 0.001,
            "total_turnover_usdc": 500.0,
            "transaction_cost_total_usdc": 5.0,
            "avg_gross_weight": 0.4,
            "max_gross_weight": 0.5,
            "strategy_instance_ids": strategy_instance_ids,
            "sleeve_run_ids": sleeve_run_ids,
            "equity_series": [{"label": "2026-03-20", "value": 10150.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "gross_return_series": [{"label": "2026-03-20", "value": 0.015}],
            "net_return_series": [{"label": "2026-03-20", "value": 0.0145}],
            "turnover_series_usdc": [{"label": "2026-03-20", "value": 500.0}],
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
            "gross_weight_series": [{"label": "2026-03-20", "value": 0.4}],
            "contribution_totals_usdc": {strategy_instance_ids[0]: 150.0},
        },
    )
    (run_dir / "weights.ndjson").write_text(
        json.dumps(
            {
                "date": "2026-03-20",
                "weights": {strategy_instance_ids[0]: 0.4},
                "cash_weight": 0.6,
                "turnover": 0.1,
                "gross_weight": 0.4,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "diagnostics.ndjson").write_text(
        json.dumps(
            {
                "date": "2026-03-20",
                "expected_returns": {strategy_instance_ids[0]: 0.01},
                "covariance_matrix": {strategy_instance_ids[0]: {strategy_instance_ids[0]: 0.001}},
                "constraint_status": "optimized",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "contributions.json",
        {
            "items": [
                {
                    "strategy_instance_id": strategy_instance_ids[0],
                    "strategy_id": "momentum",
                    "sleeve_run_id": sleeve_run_ids[0],
                    "total_gross_pnl_usdc": 155.0,
                    "daily_gross_pnl_series": [{"label": "2026-03-20", "value": 155.0}],
                }
            ],
            "transaction_cost_total_usdc": 5.0,
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
        },
    )


def test_research_control_api_flow_launches_sleeves_then_optimizer(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
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
                fingerprint="dataset-fp-1",
                source="coinbase",
                version="1",
                start=SimpleNamespace(isoformat=lambda: "2026-03-20T00:00:00+00:00"),
                end=SimpleNamespace(isoformat=lambda: "2026-03-21T00:00:00+00:00"),
            )

    sleeve_calls: list[str] = []
    portfolio_calls: list[tuple[str, ...]] = []

    def fake_load_or_run_strategy_sleeve_research(**kwargs):
        strategy_instance = kwargs["strategy_instance"]
        run_id = f"{strategy_instance.strategy_instance_id}-run"
        _write_sleeve_run(
            tmp_path,
            run_id,
            dataset_id=kwargs["dataset"].dataset_id,
            strategy_instance_id=strategy_instance.strategy_instance_id,
            strategy_id=strategy_instance.strategy_id,
        )
        sleeve_calls.append(strategy_instance.strategy_instance_id)
        return SimpleNamespace(
            run_id=run_id,
            run_dir=tmp_path / "backtests" / "sleeves" / run_id,
            analysis=SimpleNamespace(
                dataset_id=kwargs["dataset"].dataset_id,
                strategy_instance_id=strategy_instance.strategy_instance_id,
                strategy_id=strategy_instance.strategy_id,
                date_range_start="2026-03-20T00:00:00+00:00",
                date_range_end="2026-03-21T00:00:00+00:00",
                total_pnl_usdc=100.0,
                total_return_pct=0.01,
                max_drawdown_usdc=12.0,
                max_drawdown_pct=0.0012,
                daily_avg_abs_exposure_pct=(SimpleNamespace(label="2026-03-20", value=0.25),),
                daily_turnover_usdc=(SimpleNamespace(label="2026-03-20", value=150.0),),
            ),
        )

    def fake_run_portfolio_research_from_sleeves(**kwargs):
        portfolio_calls.append(tuple(kwargs["sleeve_run_ids"]))
        _write_portfolio_run(
            tmp_path,
            "portfolio-run-from-sleeves",
            dataset_id=kwargs["dataset"].dataset_id,
            sleeve_run_ids=list(kwargs["sleeve_run_ids"]),
            strategy_instance_ids=["mom-ui"],
        )
        return SimpleNamespace(run_id="portfolio-run-from-sleeves")

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr(
        "perpfut.api.routers.backtests.load_or_run_strategy_sleeve_research",
        fake_load_or_run_strategy_sleeve_research,
    )
    monkeypatch.setattr(
        "perpfut.api.routers.backtests.run_portfolio_research_from_sleeves",
        fake_run_portfolio_research_from_sleeves,
    )

    catalog_response = client.get("/api/strategy-catalog")
    sleeves_response = client.post(
        "/api/sleeves",
        json={
            "datasetId": "dataset-1",
            "strategyInstances": [
                {
                    "strategyInstanceId": "mom-ui",
                    "strategyId": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                    "strategyParams": {"lookback_candles": 12, "signal_scale": 18.0},
                    "riskOverrides": {"max_abs_position": 0.3},
                }
            ],
        },
    )
    sleeve_run_ids = [item["run_id"] for item in sleeves_response.json()["items"]]
    portfolio_response = client.post(
        "/api/portfolio-runs",
        json={
            "datasetId": "dataset-1",
            "sleeveRunIds": sleeve_run_ids,
            "startingCapitalUsdc": 10000,
            "lookbackDays": 60,
            "maxStrategyWeight": 0.4,
            "covarianceShrinkage": 0.1,
            "ridgePenalty": 0.001,
            "turnoverCostBps": 2.0,
        },
    )
    portfolio_list_response = client.get("/api/portfolio-runs", params={"datasetId": "dataset-1"})
    portfolio_detail_response = client.get("/api/portfolio-runs/portfolio-run-from-sleeves")

    assert catalog_response.status_code == 200
    assert any(item["strategyId"] == "momentum" for item in catalog_response.json()["items"])
    assert sleeves_response.status_code == 201
    assert sleeve_run_ids == ["mom-ui-run"]
    assert sleeve_calls == ["mom-ui"]
    assert portfolio_response.status_code == 201
    assert portfolio_response.json()["run_id"] == "portfolio-run-from-sleeves"
    assert portfolio_calls == [("mom-ui-run",)]
    assert portfolio_list_response.status_code == 200
    assert portfolio_list_response.json()["items"][0]["run_id"] == "portfolio-run-from-sleeves"
    assert portfolio_detail_response.status_code == 200
    assert portfolio_detail_response.json()["analysis"]["strategy_instance_ids"] == ["mom-ui"]
