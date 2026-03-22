from datetime import datetime, timedelta, timezone

from perpfut.domain import Candle
from perpfut.signal_mean_reversion import compute_signal


def test_mean_reversion_returns_negative_target_for_uptrend() -> None:
    now = datetime.now(timezone.utc)
    candles = [
        Candle(
            start=now + timedelta(minutes=index),
            low=100.0 + index,
            high=101.0 + index,
            open=100.0 + index,
            close=100.0 + index,
            volume=1_000.0,
        )
        for index in range(25)
    ]

    signal = compute_signal(candles, lookback_candles=20, signal_scale=35.0)

    assert signal.strategy == "mean_reversion"
    assert signal.raw_value > 0.0
    assert signal.target_position < 0.0


def test_mean_reversion_returns_positive_target_for_downtrend() -> None:
    now = datetime.now(timezone.utc)
    candles = [
        Candle(
            start=now + timedelta(minutes=index),
            low=100.0 - index,
            high=101.0 - index,
            open=100.0 - index,
            close=100.0 - index,
            volume=1_000.0,
        )
        for index in range(25)
    ]

    signal = compute_signal(candles, lookback_candles=20, signal_scale=35.0)

    assert signal.raw_value < 0.0
    assert signal.target_position > 0.0


def test_mean_reversion_clips_large_move() -> None:
    now = datetime.now(timezone.utc)
    candles = [
        Candle(
            start=now + timedelta(minutes=index),
            low=100.0,
            high=400.0,
            open=100.0,
            close=400.0 if index == 24 else 100.0,
            volume=1_000.0,
        )
        for index in range(25)
    ]

    signal = compute_signal(candles, lookback_candles=20, signal_scale=35.0)

    assert signal.target_position == -1.0


def test_mean_reversion_returns_zero_when_prices_are_invalid() -> None:
    now = datetime.now(timezone.utc)
    candles = [
        Candle(
            start=now + timedelta(minutes=index),
            low=0.0,
            high=0.0,
            open=0.0,
            close=0.0,
            volume=1_000.0,
        )
        for index in range(25)
    ]

    signal = compute_signal(candles, lookback_candles=20, signal_scale=35.0)

    assert signal.raw_value == 0.0
    assert signal.target_position == 0.0
