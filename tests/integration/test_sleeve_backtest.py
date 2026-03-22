import json
from datetime import datetime, timedelta, timezone

from perpfut.backtest_data import HistoricalDataset
from perpfut.config import AppConfig
from perpfut.domain import Candle
from perpfut.sleeve_backtest import load_strategy_sleeve_analysis, run_strategy_sleeve
from perpfut.strategy_instances import StrategyInstanceSpec


def _build_dataset() -> HistoricalDataset:
    anchor = datetime(2026, 3, 20, 23, 58, tzinfo=timezone.utc)
    candles_by_product = {}
    for product_id, closes in {
        "BTC-PERP-INTX": [100.0, 102.0, 104.0, 103.0, 101.0],
        "ETH-PERP-INTX": [200.0, 198.0, 196.0, 197.0, 199.0],
    }.items():
        candles = []
        for index, close in enumerate(closes):
            candles.append(
                Candle(
                    start=anchor + timedelta(minutes=index),
                    low=close - 1.0,
                    high=close + 1.0,
                    open=close,
                    close=close,
                    volume=1_000.0,
                )
            )
        candles_by_product[product_id] = tuple(candles)
    return HistoricalDataset(
        dataset_id="dataset-sleeve-1",
        created_at=anchor,
        products=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        start=anchor,
        end=anchor + timedelta(minutes=5),
        granularity="ONE_MINUTE",
        candles_by_product=candles_by_product,
    )


def test_run_strategy_sleeve_persists_daily_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    strategy_instance = StrategyInstanceSpec(
        strategy_instance_id="mom-mixed",
        strategy_id="momentum",
        universe=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        strategy_params={"lookback_candles": 2, "signal_scale": 200.0},
        risk_overrides={"max_abs_position": 0.6, "max_gross_position": 1.0},
    )

    result = run_strategy_sleeve(
        base_runs_dir=tmp_path,
        dataset=_build_dataset(),
        config=config,
        strategy_instance=strategy_instance,
    )

    manifest = json.loads((result.run_dir / "manifest.json").read_text(encoding="utf-8"))
    sleeve_analysis = json.loads(
        (result.run_dir / "sleeve_analysis.json").read_text(encoding="utf-8")
    )

    assert manifest["mode"] == "backtest"
    assert manifest["dataset_id"] == "dataset-sleeve-1"
    assert manifest["strategy_instance_id"] == "mom-mixed"
    assert manifest["strategy_instance"]["strategy_params"] == {
        "lookback_candles": 2,
        "signal_scale": 200.0,
    }
    assert manifest["config_fingerprint"] == result.config_fingerprint
    assert manifest["sleeve_analysis_path"] == "sleeve_analysis.json"
    assert result.analysis.strategy_id == "momentum"
    assert sleeve_analysis["strategy_instance_id"] == "mom-mixed"
    assert sleeve_analysis["dataset_id"] == "dataset-sleeve-1"
    assert len(sleeve_analysis["daily_returns"]) >= 1
    assert len(sleeve_analysis["daily_turnover_usdc"]) == len(sleeve_analysis["daily_returns"])
    assert len(sleeve_analysis["daily_avg_abs_exposure_pct"]) == len(
        sleeve_analysis["daily_returns"]
    )
    assert {item["product_id"] for item in sleeve_analysis["asset_contributions"]} == {
        "BTC-PERP-INTX",
        "ETH-PERP-INTX",
    }
    assert (result.run_dir / "events.ndjson").exists()
    assert (result.run_dir / "fills.ndjson").exists()
    assert (result.run_dir / "positions.ndjson").exists()
    assert (result.run_dir / "analysis.json").exists()


def test_load_strategy_sleeve_analysis_reconstructs_optimizer_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    strategy_instance = StrategyInstanceSpec(
        strategy_instance_id="mean-reversion-bucket",
        strategy_id="mean_reversion",
        universe=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        strategy_params={"lookback_candles": 2, "signal_scale": 180.0},
    )

    result = run_strategy_sleeve(
        base_runs_dir=tmp_path,
        dataset=_build_dataset(),
        config=config,
        strategy_instance=strategy_instance,
    )

    payload = load_strategy_sleeve_analysis(result.run_dir)

    assert payload["run_id"] == result.run_id
    assert payload["strategy_instance_id"] == "mean-reversion-bucket"
    assert payload["strategy_id"] == "mean_reversion"
    assert payload["config_fingerprint"] == result.config_fingerprint
    assert payload["daily_returns"]
    assert payload["daily_turnover_usdc"]
    assert payload["daily_avg_abs_exposure_pct"]
    assert payload["asset_contributions"]
