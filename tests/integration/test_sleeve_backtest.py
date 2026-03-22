import json
from datetime import datetime, timedelta, timezone

import pytest

from perpfut.backtest_data import HistoricalDataset
from perpfut.config import AppConfig
from perpfut.domain import Candle
from perpfut.sleeve_backtest import (
    compute_strategy_instance_fingerprint,
    load_strategy_sleeve_analysis,
    run_strategy_sleeve,
)
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
        fingerprint="dataset-sleeve-fingerprint",
        source="coinbase",
        version="1",
    )


def _build_multiday_dataset() -> HistoricalDataset:
    anchor = datetime(2026, 3, 20, 23, 55, tzinfo=timezone.utc)
    candles_by_product = {}
    for product_id, closes in {
        "BTC-PERP-INTX": [100.0, 103.0, 106.0, 101.0, 104.0, 108.0, 100.0, 95.0, 102.0, 110.0],
        "ETH-PERP-INTX": [200.0, 202.0, 204.0, 200.0, 201.0, 205.0, 198.0, 194.0, 199.0, 207.0],
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
        dataset_id="dataset-sleeve-multiday",
        created_at=anchor,
        products=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        start=anchor,
        end=anchor + timedelta(minutes=10),
        granularity="ONE_MINUTE",
        candles_by_product=candles_by_product,
        fingerprint="dataset-sleeve-multiday-fingerprint",
        source="coinbase",
        version="1",
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
    assert manifest["dataset_fingerprint"] == _build_dataset().fingerprint
    assert manifest["dataset_source"] == _build_dataset().source
    assert manifest["dataset_version"] == _build_dataset().version
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
    assert sleeve_analysis["dataset_fingerprint"] == _build_dataset().fingerprint
    assert sleeve_analysis["dataset_source"] == _build_dataset().source
    assert sleeve_analysis["dataset_version"] == _build_dataset().version
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


def test_strategy_instance_fingerprint_normalizes_explicit_defaults(monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "20")
    monkeypatch.setenv("SIGNAL_SCALE", "35")
    monkeypatch.setenv("MAX_ABS_POSITION", "0.5")
    monkeypatch.setenv("MAX_GROSS_POSITION", "1.0")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.10")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "10.0")
    monkeypatch.setenv("MAX_DAILY_DRAWDOWN_USDC", "250.0")
    config = AppConfig.from_env()

    implicit_defaults = StrategyInstanceSpec(
        strategy_instance_id="mom-defaults",
        strategy_id="momentum",
        universe=("BTC-PERP-INTX", "ETH-PERP-INTX"),
    )
    explicit_defaults = StrategyInstanceSpec(
        strategy_instance_id="mom-defaults",
        strategy_id="momentum",
        universe=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        strategy_params={"lookback_candles": 20, "signal_scale": 35.0},
        risk_overrides={
            "max_abs_position": 0.5,
            "max_gross_position": 1.0,
            "rebalance_threshold": 0.10,
            "min_trade_notional_usdc": 10.0,
            "max_daily_drawdown_usdc": 250.0,
        },
    )

    assert compute_strategy_instance_fingerprint(
        config=config,
        strategy_instance=implicit_defaults,
    ) == compute_strategy_instance_fingerprint(
        config=config,
        strategy_instance=explicit_defaults,
    )


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
    positions = [
        json.loads(line)
        for line in (result.run_dir / "positions.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert payload["run_id"] == result.run_id
    assert payload["strategy_instance_id"] == "mean-reversion-bucket"
    assert payload["strategy_id"] == "mean_reversion"
    assert payload["config_fingerprint"] == result.config_fingerprint
    assert payload["dataset_id"] == "dataset-sleeve-1"
    assert payload["dataset_fingerprint"] == _build_dataset().fingerprint
    assert payload["dataset_source"] == _build_dataset().source
    assert payload["dataset_version"] == _build_dataset().version
    assert payload["daily_returns"]
    assert payload["daily_turnover_usdc"]
    assert payload["daily_avg_abs_exposure_pct"]
    assert payload["asset_contributions"]

    daily_position_rows = [
        row
        for row in positions
        if row["cycle_id"].startswith("cycle-")
    ]
    expected_exposures = {}
    for row in daily_position_rows:
        portfolio = row["portfolio"]
        max_abs_notional = portfolio["equity_usdc"] * config.simulation.max_leverage
        exposure = (
            abs(portfolio["gross_notional_usdc"] / max_abs_notional)
            if abs(max_abs_notional) > 1e-12
            else 0.0
        )
        expected_exposures[row["cycle_id"]] = exposure

    actual_exposure_points = payload["daily_avg_abs_exposure_pct"]
    assert actual_exposure_points
    expected_daily_exposure = sum(expected_exposures.values()) / len(expected_exposures)
    assert actual_exposure_points[0]["value"] == pytest.approx(expected_daily_exposure)

    contribution_total = sum(
        item["total_pnl_usdc"]
        for item in payload["asset_contributions"]
    )
    assert contribution_total == pytest.approx(payload["total_pnl_usdc"])


def test_load_strategy_sleeve_analysis_preserves_multiday_drawdown_and_optimizer_inputs(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    dataset = _build_multiday_dataset()
    strategy_instance = StrategyInstanceSpec(
        strategy_instance_id="mom-multiday",
        strategy_id="momentum",
        universe=("BTC-PERP-INTX", "ETH-PERP-INTX"),
        strategy_params={"lookback_candles": 2, "signal_scale": 200.0},
        risk_overrides={"max_abs_position": 0.6, "max_gross_position": 1.0},
    )

    result = run_strategy_sleeve(
        base_runs_dir=tmp_path,
        dataset=dataset,
        config=config,
        strategy_instance=strategy_instance,
    )

    payload = load_strategy_sleeve_analysis(result.run_dir)
    events = [
        json.loads(line)
        for line in (result.run_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    expected_daily_returns = []
    expected_daily_drawdowns = []
    previous_end_equity = config.simulation.starting_collateral_usdc
    peak_equity = config.simulation.starting_collateral_usdc
    current_day = None
    current_day_end_equity = config.simulation.starting_collateral_usdc
    current_day_max_drawdown = 0.0
    for event in events:
        timestamp = datetime.fromisoformat(event["timestamp"])
        day = timestamp.date().isoformat()
        equity = float(event["portfolio"]["equity_usdc"])
        if current_day is None:
            current_day = day
        elif day != current_day:
            expected_daily_returns.append(
                {
                    "label": current_day,
                    "value": (current_day_end_equity / previous_end_equity) - 1.0,
                }
            )
            expected_daily_drawdowns.append(
                {"label": current_day, "value": current_day_max_drawdown}
            )
            previous_end_equity = current_day_end_equity
            current_day = day
            current_day_max_drawdown = 0.0
        peak_equity = max(peak_equity, equity)
        current_day_max_drawdown = max(current_day_max_drawdown, peak_equity - equity)
        current_day_end_equity = equity

    assert current_day is not None
    expected_daily_returns.append(
        {
            "label": current_day,
            "value": (current_day_end_equity / previous_end_equity) - 1.0,
        }
    )
    expected_daily_drawdowns.append(
        {"label": current_day, "value": current_day_max_drawdown}
    )

    assert payload["dataset_id"] == dataset.dataset_id
    assert payload["dataset_fingerprint"] == dataset.fingerprint
    assert payload["dataset_source"] == dataset.source
    assert payload["dataset_version"] == dataset.version
    assert [point["label"] for point in payload["daily_returns"]] == [
        point["label"] for point in expected_daily_returns
    ]
    assert [point["label"] for point in payload["daily_drawdown_usdc"]] == [
        point["label"] for point in expected_daily_drawdowns
    ]
    for actual, expected in zip(payload["daily_returns"], expected_daily_returns, strict=True):
        assert actual["value"] == pytest.approx(expected["value"])
    for actual, expected in zip(
        payload["daily_drawdown_usdc"], expected_daily_drawdowns, strict=True
    ):
        assert actual["value"] == pytest.approx(expected["value"])
    assert payload["daily_drawdown_usdc"][1]["value"] > 0.0
