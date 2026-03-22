from datetime import datetime, timedelta, timezone

from perpfut.backtest_data import HistoricalDataset
from perpfut.config import AppConfig
from perpfut.domain import Candle
from perpfut.portfolio_optimizer import (
    PortfolioOptimizationConfig,
    load_sleeve_return_stream,
    optimize_strategy_portfolio,
)
from perpfut.sleeve_backtest import load_strategy_sleeve_analysis, run_strategy_sleeve
from perpfut.strategy_instances import StrategyInstanceSpec


def _build_cross_day_dataset() -> HistoricalDataset:
    timestamps = [
        datetime(2026, 3, 20, 23, 58, tzinfo=timezone.utc),
        datetime(2026, 3, 20, 23, 59, tzinfo=timezone.utc),
        datetime(2026, 3, 21, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 21, 23, 58, tzinfo=timezone.utc),
        datetime(2026, 3, 21, 23, 59, tzinfo=timezone.utc),
        datetime(2026, 3, 22, 0, 0, tzinfo=timezone.utc),
    ]
    closes = [100.0, 102.0, 104.0, 105.0, 103.0, 101.0]
    candles = tuple(
        Candle(
            start=timestamp,
            low=close - 1.0,
            high=close + 1.0,
            open=close,
            close=close,
            volume=1_000.0,
        )
        for timestamp, close in zip(timestamps, closes)
    )
    return HistoricalDataset(
        dataset_id="dataset-cross-day",
        created_at=timestamps[0],
        products=("BTC-PERP-INTX",),
        start=timestamps[0],
        end=timestamps[-1] + timedelta(minutes=1),
        granularity="ONE_MINUTE",
        candles_by_product={"BTC-PERP-INTX": candles},
        fingerprint="cross-day-fingerprint",
        source="coinbase",
        version="1",
    )


def test_optimizer_uses_utc_daily_labels_from_real_sleeve_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "150")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    sleeve = run_strategy_sleeve(
        base_runs_dir=tmp_path,
        dataset=_build_cross_day_dataset(),
        config=config,
        strategy_instance=StrategyInstanceSpec(
            strategy_instance_id="mom-cross-day",
            strategy_id="momentum",
            universe=("BTC-PERP-INTX",),
            strategy_params={"lookback_candles": 2, "signal_scale": 150.0},
        ),
    )

    sleeve_payload = load_strategy_sleeve_analysis(sleeve.run_dir)
    result = optimize_strategy_portfolio(
        [load_sleeve_return_stream(sleeve_payload)],
        config=PortfolioOptimizationConfig(
            lookback_days=1,
            max_strategy_weight=1.0,
            turnover_cost_bps=0.0,
        ),
    )

    assert [point["label"] for point in sleeve_payload["daily_returns"]] == [
        "2026-03-21",
        "2026-03-22",
    ]
    assert [point.label for point in result.daily_net_returns] == [
        "2026-03-21",
        "2026-03-22",
    ]
    assert [snapshot.date for snapshot in result.weight_history] == [
        "2026-03-21",
        "2026-03-22",
    ]
