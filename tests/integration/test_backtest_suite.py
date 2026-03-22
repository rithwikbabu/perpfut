import json
from datetime import datetime, timedelta, timezone

from perpfut.backtest_data import HistoricalDataset
from perpfut.backtest_suite import BacktestSuiteRunner
from perpfut.config import AppConfig
from perpfut.domain import Candle


def _build_dataset() -> HistoricalDataset:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    candles_by_product = {}
    for product_id, closes in {
        "BTC-PERP-INTX": [100.0, 101.0, 102.0, 103.0],
        "ETH-PERP-INTX": [200.0, 199.0, 198.0, 197.0],
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
        dataset_id="dataset-1",
        created_at=anchor,
        products=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        start=anchor,
        end=anchor + timedelta(minutes=4),
        granularity="ONE_MINUTE",
        candles_by_product=candles_by_product,
    )


def test_backtest_suite_runner_persists_runs_and_suite_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    runner = BacktestSuiteRunner(
        base_runs_dir=tmp_path,
        dataset=_build_dataset(),
        config=config,
    )

    result = runner.run_suite(strategy_ids=["momentum", "mean_reversion"])

    suite_dir = tmp_path / "backtests" / "suites" / result.suite_id
    suite_manifest = json.loads((suite_dir / "manifest.json").read_text(encoding="utf-8"))

    assert suite_manifest["dataset_id"] == "dataset-1"
    assert suite_manifest["strategies"] == ["momentum", "mean_reversion"]
    assert len(result.run_ids) == 2
    for item in result.items:
        run_dir = tmp_path / "backtests" / "runs" / item.run_id
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
        assert manifest["mode"] == "backtest"
        assert manifest["suite_id"] == result.suite_id
        assert manifest["dataset_id"] == "dataset-1"
        assert manifest["products"] == ["BTC-PERP-INTX", "ETH-PERP-INTX"]
        assert state["portfolio"]["equity_usdc"] == analysis["ending_equity_usdc"]
        assert (run_dir / "events.ndjson").exists()
        assert (run_dir / "fills.ndjson").exists()
        assert (run_dir / "positions.ndjson").exists()


def test_backtest_suite_runner_rejects_empty_executable_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "10")
    config = AppConfig.from_env()
    runner = BacktestSuiteRunner(
        base_runs_dir=tmp_path,
        dataset=_build_dataset(),
        config=config,
    )

    try:
        runner.run_suite(strategy_ids=["momentum"])
    except ValueError as exc:
        assert "no executable cycles" in str(exc)
    else:
        raise AssertionError("expected suite runner to reject empty executable datasets")

    assert not (tmp_path / "backtests" / "suites").exists()
    runs_dir = tmp_path / "backtests" / "runs"
    assert not runs_dir.exists() or not list(runs_dir.iterdir())


def test_backtest_suite_runner_rejects_empty_strategy_list(tmp_path) -> None:
    runner = BacktestSuiteRunner(
        base_runs_dir=tmp_path,
        dataset=_build_dataset(),
        config=AppConfig.from_env(),
    )

    try:
        runner.run_suite(strategy_ids=[])
    except ValueError as exc:
        assert "at least one strategy" in str(exc)
    else:
        raise AssertionError("expected suite runner to reject empty strategy lists")

    assert not (tmp_path / "backtests" / "suites").exists()
