"""Pure signal logic for a baseline mean-reversion strategy."""

from __future__ import annotations

from collections.abc import Sequence

from .domain import Candle, SignalDecision

STRATEGY_ID = "mean_reversion"


def compute_signal(
    candles: Sequence[Candle],
    *,
    lookback_candles: int,
    signal_scale: float,
) -> SignalDecision:
    if len(candles) < lookback_candles:
        return SignalDecision(strategy=STRATEGY_ID, raw_value=0.0, target_position=0.0)

    window = candles[-lookback_candles:]
    starting_price = window[0].close
    ending_price = window[-1].close

    if starting_price <= 0.0:
        return SignalDecision(strategy=STRATEGY_ID, raw_value=0.0, target_position=0.0)

    raw_return = (ending_price / starting_price) - 1.0
    target_position = max(-1.0, min(1.0, -(raw_return * signal_scale)))
    return SignalDecision(
        strategy=STRATEGY_ID,
        raw_value=raw_return,
        target_position=target_position,
    )
