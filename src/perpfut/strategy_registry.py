"""Registry-backed strategy dispatch."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .config import StrategyConfig
from .domain import Candle, SignalDecision
from .signal_mean_reversion import STRATEGY_ID as MEAN_REVERSION_STRATEGY_ID
from .signal_mean_reversion import compute_signal as compute_mean_reversion_signal
from .signal_momentum import STRATEGY_ID as MOMENTUM_STRATEGY_ID
from .signal_momentum import compute_signal as compute_momentum_signal


StrategyHandler = Callable[[Sequence[Candle], StrategyConfig], SignalDecision]


def compute_strategy_signal(
    candles: Sequence[Candle],
    strategy: StrategyConfig,
) -> SignalDecision:
    validate_strategy_id(strategy.strategy_id)
    handler = STRATEGY_REGISTRY[strategy.strategy_id]
    return handler(candles, strategy)


def validate_strategy_id(strategy_id: str) -> None:
    try:
        STRATEGY_REGISTRY[strategy_id]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise ValueError(
            f"unknown strategy_id '{strategy_id}'; available strategies: {available}"
        ) from exc


def _compute_momentum(candles: Sequence[Candle], strategy: StrategyConfig) -> SignalDecision:
    return compute_momentum_signal(
        candles,
        lookback_candles=strategy.lookback_candles,
        signal_scale=strategy.signal_scale,
    )


def _compute_mean_reversion(
    candles: Sequence[Candle],
    strategy: StrategyConfig,
) -> SignalDecision:
    return compute_mean_reversion_signal(
        candles,
        lookback_candles=strategy.lookback_candles,
        signal_scale=strategy.signal_scale,
    )


STRATEGY_REGISTRY: dict[str, StrategyHandler] = {
    MOMENTUM_STRATEGY_ID: _compute_momentum,
    MEAN_REVERSION_STRATEGY_ID: _compute_mean_reversion,
}
