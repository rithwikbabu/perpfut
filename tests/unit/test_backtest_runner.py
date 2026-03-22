from datetime import datetime, timedelta, timezone

from perpfut.backtest_data import HistoricalDataset
from perpfut.backtest_runner import (
    SharedCapitalBacktestRunner,
    allocate_target_positions,
)
from perpfut.config import AppConfig
from perpfut.domain import Candle, Mode


def _build_dataset(*, products: dict[str, list[float]]) -> HistoricalDataset:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    candles_by_product = {}
    for product_id, closes in products.items():
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
        products=tuple(products.keys()),
        start=anchor,
        end=anchor + timedelta(minutes=len(next(iter(products.values())))),
        granularity="ONE_MINUTE",
        candles_by_product=candles_by_product,
    )


def test_allocate_target_positions_scales_gross_exposure() -> None:
    allocated = allocate_target_positions(
        {
            "BTC-PERP-INTX": 0.6,
            "ETH-PERP-INTX": -0.6,
        },
        max_gross_position=1.0,
    )

    assert round(sum(abs(value) for value in allocated.values()), 6) == 1.0
    assert allocated["BTC-PERP-INTX"] == 0.5
    assert allocated["ETH-PERP-INTX"] == -0.5


def test_shared_capital_backtest_runner_uses_next_bar_open_fills_without_lookahead(monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    dataset = _build_dataset(products={"BTC-PERP-INTX": [100.0, 101.0, 102.0, 103.0]})
    runner = SharedCapitalBacktestRunner(config=config, dataset=dataset)

    results = runner.run()

    assert len(results) == 2
    first_cycle = results[0]
    first_asset = first_cycle.assets["BTC-PERP-INTX"]
    assert first_cycle.mode is Mode.BACKTEST
    assert first_asset.fill is not None
    assert first_asset.fill.mark_price == 102.0
    assert first_asset.fill.price == 102.0
    assert first_asset.execution_summary.action == "filled"


def test_shared_capital_backtest_runner_clips_mixed_book_gross_exposure(monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    monkeypatch.setenv("MAX_ABS_POSITION", "0.6")
    monkeypatch.setenv("MAX_GROSS_POSITION", "1.0")
    config = AppConfig.from_env()
    dataset = _build_dataset(
        products={
            "BTC-PERP-INTX": [100.0, 101.0, 102.0, 103.0],
            "ETH-PERP-INTX": [200.0, 199.0, 198.0, 197.0],
        }
    )
    runner = SharedCapitalBacktestRunner(config=config, dataset=dataset)

    results = runner.run()

    first_cycle = results[0]
    assert first_cycle.portfolio.gross_notional_usdc <= (
        config.simulation.starting_collateral_usdc * config.simulation.max_leverage
    )
    assert set(first_cycle.assets) == {"BTC-PERP-INTX", "ETH-PERP-INTX"}
    assert first_cycle.assets["BTC-PERP-INTX"].fill is not None
    assert first_cycle.assets["ETH-PERP-INTX"].fill is not None


def test_shared_capital_backtest_runner_uses_selected_products_for_alignment(monkeypatch) -> None:
    monkeypatch.setenv("LOOKBACK_CANDLES", "2")
    monkeypatch.setenv("SIGNAL_SCALE", "200")
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.0")
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "0.0")
    monkeypatch.setenv("SLIPPAGE_BPS", "0.0")
    config = AppConfig.from_env()
    dataset = _build_dataset(
        products={
            "BTC-PERP-INTX": [100.0, 101.0, 102.0, 103.0],
            "ETH-PERP-INTX": [200.0, 201.0, 202.0, 203.0],
            "SOL-PERP-INTX": [50.0, 51.0, 53.0],
        }
    )
    runner = SharedCapitalBacktestRunner(
        config=config,
        dataset=dataset,
        products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
    )

    results = runner.run()

    assert len(results) == 2
    assert set(results[0].assets) == {"BTC-PERP-INTX", "ETH-PERP-INTX"}
