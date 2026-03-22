import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from perpfut.api import create_app


def _write_dataset(runs_dir: Path, dataset_id: str = "dataset-1") -> Path:
    dataset_dir = runs_dir / "backtests" / "datasets" / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": dataset_id,
                "created_at": "2026-03-22T00:00:00+00:00",
                "fingerprint": "dataset-fp-1",
                "source": "coinbase",
                "version": "1",
                "products": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                "start": "2026-03-01T00:00:00+00:00",
                "end": "2026-03-10T00:00:00+00:00",
                "granularity": "ONE_MINUTE",
                "candle_counts": {"BTC-PERP-INTX": 10, "ETH-PERP-INTX": 10},
            }
        ),
        encoding="utf-8",
    )
    return dataset_dir


def test_strategy_catalog_lists_supported_builder_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    client = TestClient(create_app())

    response = client.get("/api/strategy-catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 2
    momentum = next(item for item in payload["items"] if item["strategyId"] == "momentum")
    assert momentum["label"] == "Momentum"
    assert {field["key"] for field in momentum["strategyParams"]} == {
        "lookback_candles",
        "signal_scale",
    }
    assert {field["key"] for field in momentum["riskOverrides"]} == {
        "max_abs_position",
        "max_gross_position",
        "rebalance_threshold",
        "min_trade_notional_usdc",
        "max_daily_drawdown_usdc",
    }


def test_launch_sleeves_creates_and_reuses_strategy_sleeves(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _write_dataset(tmp_path)
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
            return SimpleNamespace(dataset_id=dataset_id)

    calls: list[str] = []

    def fake_load_or_run_strategy_sleeve_research(**kwargs):
        strategy_instance = kwargs["strategy_instance"]
        run_id = f"{strategy_instance.strategy_instance_id}-run"
        run_dir = tmp_path / "backtests" / "sleeves" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"created_at": "2026-03-22T00:00:00+00:00"}),
            encoding="utf-8",
        )
        calls.append(strategy_instance.strategy_instance_id)
        return SimpleNamespace(
            run_id=run_id,
            run_dir=run_dir,
            analysis=SimpleNamespace(
                dataset_id="dataset-1",
                strategy_instance_id=strategy_instance.strategy_instance_id,
                strategy_id=strategy_instance.strategy_id,
                date_range_start="2026-03-01T00:00:00+00:00",
                date_range_end="2026-03-10T00:00:00+00:00",
                total_pnl_usdc=125.0,
                total_return_pct=0.0125,
                max_drawdown_usdc=15.0,
                max_drawdown_pct=0.0015,
                daily_avg_abs_exposure_pct=(
                    SimpleNamespace(label="2026-03-01", value=0.35),
                    SimpleNamespace(label="2026-03-02", value=0.45),
                ),
                daily_turnover_usdc=(
                    SimpleNamespace(label="2026-03-01", value=100.0),
                    SimpleNamespace(label="2026-03-02", value=125.0),
                ),
            ),
        )

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr(
        "perpfut.api.routers.backtests.load_or_run_strategy_sleeve_research",
        fake_load_or_run_strategy_sleeve_research,
    )

    response = client.post(
        "/api/sleeves",
        json={
            "datasetId": "dataset-1",
            "strategyInstances": [
                {
                    "strategyInstanceId": "mom-a",
                    "strategyId": "momentum",
                    "universe": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
                    "strategyParams": {"lookback_candles": 12, "signal_scale": 20.0},
                },
                {
                    "strategyInstanceId": "mr-b",
                    "strategyId": "mean_reversion",
                    "universe": ["BTC-PERP-INTX"],
                },
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["count"] == 2
    assert [item["run_id"] for item in payload["items"]] == ["mom-a-run", "mr-b-run"]
    assert payload["items"][0]["created_at"] == "2026-03-22T00:00:00+00:00"
    assert payload["items"][0]["avg_abs_exposure_pct"] == 0.4
    assert payload["items"][0]["turnover_usdc"] == 225.0
    assert calls == ["mom-a", "mr-b"]


def test_launch_sleeves_returns_404_for_missing_dataset(monkeypatch, tmp_path) -> None:
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
            raise FileNotFoundError(f"backtest dataset not found: {dataset_id}")

    monkeypatch.setattr("perpfut.api.routers.backtests.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.api.routers.backtests.HistoricalDatasetBuilder", FakeBuilder)

    response = client.post(
        "/api/sleeves",
        json={
            "datasetId": "missing-dataset",
            "strategyInstances": [
                {
                    "strategyInstanceId": "mom-a",
                    "strategyId": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                }
            ],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "backtest dataset not found: missing-dataset"
