from datetime import datetime, timedelta, timezone

from perpfut.backtest_data import HistoricalDataset
from perpfut.config import AppConfig
from perpfut.domain import Candle
from perpfut.portfolio_optimizer import PortfolioOptimizationConfig
from perpfut.portfolio_runs import run_portfolio_research
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


def test_run_portfolio_research_persists_artifacts_and_reuses_cached_sleeves(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "150")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")

    config = AppConfig.from_env()
    dataset = _build_cross_day_dataset()
    strategy_instances = (
        StrategyInstanceSpec(
            strategy_instance_id="mom-a",
            strategy_id="momentum",
            universe=("BTC-PERP-INTX",),
            strategy_params={"lookback_candles": 2, "signal_scale": 150.0},
        ),
    )

    first = run_portfolio_research(
        base_runs_dir=tmp_path,
        dataset=dataset,
        config=config,
        strategy_instances=strategy_instances,
        optimizer_config=PortfolioOptimizationConfig(
            lookback_days=1,
            max_strategy_weight=1.0,
            turnover_cost_bps=0.0,
        ),
        starting_capital_usdc=10_000.0,
    )
    second = run_portfolio_research(
        base_runs_dir=tmp_path,
        dataset=dataset,
        config=config,
        strategy_instances=strategy_instances,
        optimizer_config=PortfolioOptimizationConfig(
            lookback_days=1,
            max_strategy_weight=1.0,
            turnover_cost_bps=0.0,
        ),
        starting_capital_usdc=10_000.0,
    )

    assert (first.run_dir / "analysis.json").exists()
    assert (first.run_dir / "weights.ndjson").exists()
    assert (first.run_dir / "diagnostics.ndjson").exists()
    assert (first.run_dir / "contributions.json").exists()
    assert first.analysis.strategy_instance_ids == ("mom-a",)
    assert second.sleeve_run_ids == first.sleeve_run_ids
