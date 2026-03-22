from datetime import datetime, timedelta, timezone

import pytest

from perpfut.config import StrategyConfig
from perpfut.domain import Candle
from perpfut.signal_mean_reversion import compute_signal as compute_mean_reversion_signal
from perpfut.signal_momentum import compute_signal as compute_momentum_signal
from perpfut.strategy_registry import compute_strategy_signal


def _build_candles(count: int = 25) -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [
        Candle(
            start=now + timedelta(minutes=index),
            low=100.0 + index,
            high=101.0 + index,
            open=100.0 + index,
            close=100.0 + index,
            volume=1_000.0,
        )
        for index in range(count)
    ]


def test_registry_dispatch_preserves_momentum_behavior() -> None:
    candles = _build_candles()
    strategy = StrategyConfig(strategy_id="momentum", lookback_candles=20, signal_scale=35.0)

    direct = compute_momentum_signal(candles, lookback_candles=20, signal_scale=35.0)
    dispatched = compute_strategy_signal(candles, strategy)

    assert dispatched == direct


def test_registry_rejects_unknown_strategy() -> None:
    candles = _build_candles()
    strategy = StrategyConfig(strategy_id="unknown", lookback_candles=20, signal_scale=35.0)

    with pytest.raises(ValueError, match="unknown strategy_id"):
        compute_strategy_signal(candles, strategy)


def test_registry_dispatches_mean_reversion() -> None:
    candles = _build_candles()
    strategy = StrategyConfig(strategy_id="mean_reversion", lookback_candles=20, signal_scale=35.0)

    direct = compute_mean_reversion_signal(candles, lookback_candles=20, signal_scale=35.0)
    dispatched = compute_strategy_signal(candles, strategy)

    assert dispatched == direct
